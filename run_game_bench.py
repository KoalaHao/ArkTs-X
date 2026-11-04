"""Build and compare persistent game-world CPU ticks on macOS ARM64 or Linux/WSL2."""
import argparse
import datetime
import hashlib
import json
import math
import os
import pathlib
import platform
import random
import re
import statistics
import signal
import subprocess
import time

from game_references import references
import hostinfo

ROOT = pathlib.Path(__file__).resolve().parent
OUTPUT = ROOT / 'results/game'

def capture(args):
    return subprocess.check_output(args, cwd=ROOT, text=True).strip()

def percentile(values, fraction):
    ordered = sorted(values)
    return ordered[max(0, math.ceil(len(ordered) * fraction) - 1)]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--runs', type=int, default=3)
    args = parser.parse_args()
    if args.runs < 1:
        raise SystemExit('--runs must be positive')
    OUTPUT.mkdir(parents=True, exist_ok=True)
    compiler = ROOT / 'build/ark-source/bin/es2panda_stdlib_compiler'
    ark = ROOT / 'build/ark-source/bin/ark'
    stdlib = ROOT / 'build/ark-source/plugins/ets/etsstdlib.abc'
    commands = [
        ['python3', 'generate_game_dart.py'],
        ['dart', 'format', 'bench/game.dart'],
        ['dart', 'analyze', 'bench/game.dart'],
        ['dart', 'compile', 'exe', 'bench/game.dart', '-o', 'build/game_dart_aot'],
        ['dart', 'compile', 'kernel', 'bench/game.dart', '-o', 'build/game.dill'],
        [str(compiler), '--extension=ets', '--opt-level=2',
         '--output=' + str(ROOT / 'build/game.abc'), str(ROOT / 'bench/game.ets')],
    ]
    with (ROOT / 'build/game-build.log').open('w') as log:
        for command in commands:
            process = subprocess.run(command, cwd=ROOT, stdout=log, stderr=log)
            if process.returncode:
                raise SystemExit('Build failed; see build/game-build.log')
    print('All three modes built; Dart analysis passed. Computing independent references.', flush=True)
    expected = references()
    modes = {
        'dart-jit': ['dart', str(ROOT / 'build/game.dill')],
        'dart-aot': [str(ROOT / 'build/game_dart_aot')],
        'ark-jit': [str(ark), '--load-runtimes=ets', '--boot-panda-files=' + str(stdlib),
                    '--compiler-enable-jit=true', str(ROOT / 'build/game.abc'), 'game.ETSGLOBAL::main'],
    }
    artifact_paths = [ROOT / path for path in (
        'bench/game.ets', 'bench/game.dart', 'game_references.py', 'generate_game_dart.py',
        'run_game_bench.py', 'build/game.dill', 'build/game_dart_aot', 'build/game.abc',
        'build/ark-source/bin/ark', 'build/ark-source/bin/es2panda_stdlib_compiler',
        'build/ark-source/plugins/ets/etsstdlib.abc', hostinfo.TOOLCHAIN, 'native/macos-port.patch')]
    artifact_paths += [path for path in hostinfo.runtime_libs() if path.exists()]
    metadata = {
        'timestamp': datetime.datetime.now().astimezone().isoformat(),
        'platform': platform.platform(), 'architecture': platform.machine(),
        'cpu': hostinfo.cpu_name(), 'wsl': hostinfo.is_wsl(),
        'dart': capture(['dart', '--version']), 'commands': modes, 'build_commands': commands,
        'runtime_commit': capture(['git', '-C', 'vendor/runtime_core', 'rev-parse', 'HEAD']),
        'frontend_commit': capture(['git', '-C', 'vendor/ets_frontend', 'rev-parse', 'HEAD']),
        'ark_managed_pointer_bits': hostinfo.MANAGED_POINTER_BITS, 'references': expected,
        'method': 'one workload per fresh process; persistent worlds; 1s warmup; fresh world; 3000 unpaced CPU ticks; monotonic clocks; checkpoints before and after timing',
        'percentile': 'nearest rank; p50 uses median; summaries are medians of process metrics',
        'artifact_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in artifact_paths},
    }
    results = []
    for run in range(args.runs):
        order = [(mode, name) for mode in modes for name in expected]
        random.Random(1291 + run).shuffle(order)
        for mode, case in order:
            command = [*hostinfo.TIME_PREFIX, *modes[mode],
                       *(['--'] if mode == 'ark-jit' else []), case]
            started = time.perf_counter()
            stdout_path = OUTPUT / f'{mode}-{case}-{run+1}.stdout'
            stderr_path = OUTPUT / f'{mode}-{case}-{run+1}.stderr'
            with stdout_path.open('w') as stdout, stderr_path.open('w') as stderr:
                child = subprocess.Popen(command, cwd=ROOT,
                                         stdout=stdout, stderr=stderr, start_new_session=True)
                try:
                    returncode = child.wait(timeout=180)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGTERM)
                    child.wait()
                    raise SystemExit(f'{mode} timed out; partial stage/output logs saved in {OUTPUT}')
            wall = time.perf_counter() - started
            stdout_text = stdout_path.read_text()
            stderr_text = stderr_path.read_text()
            if returncode:
                raise SystemExit(f'{mode} failed ({returncode}): {stderr_text[-3000:]}')
            rows = []
            seen = set()
            for line in stdout_text.splitlines():
                if not line.startswith('GAME '):
                    continue
                row = json.loads(line[5:])
                name = row['name']
                if name not in expected or name in seen:
                    raise SystemExit(f'Unexpected or repeated case: {name}')
                seen.add(name)
                for key in ('check_before', 'check_after'):
                    if len(row[key]) != 2 or any(not math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-7)
                                                 for a, b in zip(row[key], expected[name])):
                        raise SystemExit(f'{mode} {name} {key} mismatch: {row[key]} != {expected[name]}')
                samples = row['frames_ms']
                if (len(samples) != 3000 or any(not math.isfinite(v) or v <= 0 for v in samples)
                        or not math.isfinite(row['sink']) or row['sink'] == 0
                        or not math.isfinite(row['warm_sink'])):
                    raise SystemExit(f'{mode} {name}: invalid timing or unconsumed work')
                row['p50_ms'] = statistics.median(samples)
                row['p95_ms'] = percentile(samples, .95)
                row['p99_ms'] = percentile(samples, .99)
                row['max_ms'] = max(samples)
                row['ticks_over_16_67ms'] = sum(v > 1000 / 60 for v in samples)
                rows.append(row)
            if seen != {case}:
                raise SystemExit(f'{mode}: expected only {case}, got {seen}')
            measured = sum(sum(row['frames_ms']) for row in rows) / 1000
            if measured + .95 > wall * 1.05:
                raise SystemExit(f'{mode}: monotonic clock units/warmup disagree with process wall time')
            rss = hostinfo.peak_rss_bytes(stderr_text)
            if rss is None:
                raise SystemExit('Missing native peak RSS')
            results.append({'mode': mode, 'case': case, 'command': command, 'run': run+1, 'wall_s': wall,
                            'peak_rss_bytes': rss, 'benchmarks': rows})
            (OUTPUT / 'results.json').write_text(json.dumps({'metadata': metadata, 'runs': results}, indent=2))
            print(mode, run+1, {row['name']: [round(row['p50_ms'],4), round(row['p99_ms'],4)]
                                for row in rows}, flush=True)
    lines = ['| CPU workload (p50 / p99 ms) | ' + ' | '.join(modes) + ' |',
             '|---|' + '---:|' * len(modes)]
    for name in expected:
        cells = []
        for mode in modes:
            rows = [b for run in results if run['mode'] == mode for b in run['benchmarks'] if b['name'] == name]
            cells.append(' / '.join(f'{statistics.median(b[k] for b in rows):.4f}' for k in ('p50_ms', 'p99_ms')))
        lines.append('| ' + name + ' | ' + ' | '.join(cells) + ' |')
    (OUTPUT / 'table.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))

if __name__ == '__main__':
    main()
