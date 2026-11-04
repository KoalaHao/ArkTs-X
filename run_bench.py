"""Run native macOS suites serially, validate checksums, retain raw samples."""
import argparse
import datetime
import hashlib
import json
import math
import pathlib
import platform
import random
import re
import statistics
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parent

def capture(args):
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()

def references():
    flags = bytearray(200001)
    for p in range(2, math.isqrt(200000) + 1):
        if not flags[p]:
            flags[p*p::p] = bytes([1]) * len(flags[p*p::p])
    sieve = sum(not b for b in flags[2:])
    x = [(i % 97) * .125 + 1 for i in range(32768)]
    y = [(i % 53) * .25 for i in range(32768)]
    for _ in range(12):
        for i in range(len(x)):
            x[i] = x[i] * .999 + y[i] * .001
            y[i] = y[i] * .998 + x[i] * .002
    vectors = sum(a+b for a,b in zip(x,y))
    objects = 0
    for i in range(10000):
        weight, state = (i % 31) * .25 + 1, i % 4
        for _ in range(4):
            weight = weight * 1.001 + state
            state = (state + 1) % 4
        objects += weight + i
    text = 1 + sum(len(f'review src/agent_{i%97}.dart 内容') *
                   (3 if i%7 == 0 else 1) for i in range(4096))
    return dict(sieve=sieve, vectors=vectors, objects=objects, text=text)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--dart-only', action='store_true')
    args = parser.parse_args()
    ark = ROOT / 'build/ark-source/bin/ark'
    compiler = ROOT / 'build/ark-source/bin/es2panda_stdlib_compiler'
    stdlib = ROOT / 'build/ark-source/plugins/ets/etsstdlib.abc'
    kernel = ROOT / 'build/suite.dill'
    kernel_compile = ['dart', 'compile', 'kernel', str(ROOT / 'bench/suite.dart'),
                       '-o', str(kernel)]
    capture(kernel_compile)
    modes = {
        'dart-jit': ['dart', str(kernel)],
        'dart-aot': [str(ROOT / 'build/dart_aot')],
    }
    if not args.dart_only:
        for path in (ark, compiler, stdlib):
            if not path.exists():
                raise SystemExit(f'Source-built Ark artifact missing: {path}')
        capture([str(compiler), '--extension=ets', '--opt-level=2',
                 '--output=' + str(ROOT / 'build/suite.abc'),
                 str(ROOT / 'bench/suite.ets')])
        modes['ark-static-jit'] = [str(ark), '--load-runtimes=ets',
            '--boot-panda-files=' + str(stdlib), '--compiler-enable-jit=true',
            str(ROOT / 'build/suite.abc'), 'suite.ETSGLOBAL::main']
    expected = references()
    metadata = {
        'timestamp': datetime.datetime.now().astimezone().isoformat(),
        'platform': platform.platform(), 'architecture': platform.machine(),
        'cpu': capture(['sysctl', '-n', 'machdep.cpu.brand_string']),
        'dart': capture(['dart', '--version']),
        'runtime_commit': capture(['git', '-C', 'vendor/runtime_core',
                                   'rev-parse', 'HEAD']),
        'frontend_commit': capture(['git', '-C', 'vendor/ets_frontend',
                                    'rev-parse', 'HEAD']),
        'commands': modes, 'references': expected,
        'dart_kernel_compile_command': kernel_compile,
        'method': '1s warmup, 5 adaptive-batch samples per process; serial runs',
    }
    artifacts = [ROOT / 'build/dart_aot', kernel]
    if not args.dart_only:
        artifacts.extend([ark, compiler, stdlib, ROOT / 'build/suite.abc'])
        artifacts.extend(ROOT / 'build/ark-source/lib' / name for name in (
            'libarkruntime.dylib', 'libarkbase.dylib',
            'libarkaotmanager.dylib', 'libarktarget_options.dylib'))
        metadata['ark_managed_pointer_bits'] = 64
        metadata['ark_binary_format'] = capture(['file', str(ark)])
        metadata['local_port_patch_sha256'] = hashlib.sha256(
            (ROOT / 'native/macos-port.patch').read_bytes()).hexdigest()
        metadata['toolchain_sha256'] = hashlib.sha256(
            (ROOT / 'native/macos-arm64.cmake').read_bytes()).hexdigest()
    metadata['artifact_sha256'] = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in artifacts
    }
    results = []
    for run in range(args.runs):
        order = list(modes)
        random.Random(841 + run).shuffle(order)
        for mode in order:
            command = ['/usr/bin/time', '-l'] + modes[mode]
            start = time.perf_counter()
            process = subprocess.run(command, cwd=ROOT, capture_output=True,
                                     text=True, timeout=180)
            wall = time.perf_counter() - start
            stem = ROOT / 'results' / f'{mode}-{run+1}'
            stem.with_suffix('.stdout').write_text(process.stdout)
            stem.with_suffix('.stderr').write_text(process.stderr)
            if process.returncode:
                raise SystemExit(f'{mode} failed: {process.stderr[-3000:]}')
            rows = []
            for line in process.stdout.splitlines():
                if not line.startswith('BENCH '):
                    continue
                row = json.loads(line[6:])
                if not math.isclose(row['check'], expected[row['name']],
                                    rel_tol=1e-10, abs_tol=1e-8):
                    raise SystemExit(f'Checksum mismatch: {mode}: {row}')
                if (not row['sink'] > 0 or len(row['ms_per_op']) != 5 or
                        any(not math.isfinite(value) or value <= 0 for value in row['ms_per_op'])):
                    raise SystemExit(f'Invalid sample: {mode}: {row}')
                rows.append(row)
            if len(rows) != 4:
                raise SystemExit(f'Expected 4 benchmarks: {process.stdout}')
            match = re.search(r'(\d+)\s+maximum resident set size',process.stderr)
            results.append({'mode': mode, 'run': run+1, 'wall_s': wall,
                'peak_rss_bytes': int(match[1]) if match else None,
                'benchmarks': rows})
            (ROOT / 'results/results.json').write_text(json.dumps(
                {'metadata':metadata,'runs':results}, indent=2))
            print(mode, run+1, {r['name']: round(statistics.median(
                r['ms_per_op']), 4) for r in rows}, flush=True)
    lines = ['| Workload | ' + ' | '.join(modes) + ' |',
             '|---|' + '---:|' * len(modes)]
    for name in expected:
        values = []
        for mode in modes:
            per_process = [statistics.median(row['ms_per_op'])
                for result in results if result['mode'] == mode
                for row in result['benchmarks'] if row['name'] == name]
            values.append(f'{statistics.median(per_process):.4f} ms')
        lines.append('| ' + name + ' | ' + ' | '.join(values) + ' |')
    report = '\n'.join(lines) + '\n'
    (ROOT / 'results/table.md').write_text(report)
    print(report)

if __name__ == '__main__':
    main()
