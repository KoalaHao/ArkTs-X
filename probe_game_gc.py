"""Instrumented GC diagnostics; these are not primary benchmark timings.

Builds copies of the same kernels with one extra measured-end marker, enables
collector logs, and keeps only logs completed inside the measured stage.
"""
import hashlib
import json
import os
import pathlib
import shutil
import signal
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / 'results/game/gc'
OUT.mkdir(parents=True, exist_ok=True)
for language, declaration in [('dart', 'final'), ('ets', 'const')]:
    source = (ROOT / f'bench/game.{language}').read_text()
    needle = f'{declaration} after = checkWorld(kind);'
    assert source.count(needle) == 1
    printer = "print('GC_MEASURE_END');" if language == 'dart' else "console.log('GC_MEASURE_END');"
    source = source.replace(needle, printer + '\n  ' + needle)
    (ROOT / f'build/game_gc_probe.{language}').write_text(source)

sdk = pathlib.Path(shutil.which('dart')).resolve().parent
compiler = ROOT / 'build/ark-source/bin/es2panda_stdlib_compiler'
builds = [
    ['dart', 'compile', 'kernel', 'build/game_gc_probe.dart', '-o', 'build/game_gc_probe.dill'],
    ['dart', 'compile', 'aot-snapshot', 'build/game_gc_probe.dart', '-o', 'build/game_gc_probe.aot'],
    [str(compiler), '--extension=ets', '--opt-level=2', '--output=build/game_gc_probe.abc',
     'build/game_gc_probe.ets'],
]
with (ROOT / 'build/game-gc-build.log').open('w') as log:
    for command in builds:
        subprocess.run(command, cwd=ROOT, stdout=log, stderr=log, check=True)

modes = {
    'dart-jit': ['dart', '--verbose_gc', str(ROOT / 'build/game_gc_probe.dill')],
    'dart-aot': [str(sdk / 'dartaotruntime'), '--verbose_gc', str(ROOT / 'build/game_gc_probe.aot')],
    'ark-jit': [str(ROOT / 'build/ark-source/bin/ark'), '--load-runtimes=ets',
                '--boot-panda-files=' + str(ROOT / 'build/ark-source/plugins/ets/etsstdlib.abc'),
                '--compiler-enable-jit=true', '--log-info=gc', str(ROOT / 'build/game_gc_probe.abc'),
                'game_gc_probe.ETSGLOBAL::main', '--'],
}
receipts = []
for case in ('events_alloc_2k', 'events_pool_2k'):
    for mode, base in modes.items():
        command = [*base, case]
        path = OUT / f'{mode}-{case}.log'
        with path.open('w') as log:
            process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=log, start_new_session=True)
            try:
                code = process.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait()
                raise SystemExit(f'GC diagnostic timed out: {path}')
        if code:
            raise SystemExit(f'GC diagnostic failed: {path}, exit {code}')
        text = path.read_text()
        measured = text.split(f'GAME_STAGE {case} measured\n', 1)[1].split('GC_MEASURE_END', 1)[0]
        (OUT / f'{mode}-{case}.measured.log').write_text(measured)
        row = json.loads(next(line[5:] for line in text.splitlines() if line.startswith('GAME ')))
        reference = json.loads((ROOT / 'results/game/results.json').read_text())['metadata']['references'][case]
        assert row['check_before'] == reference and row['check_after'] == reference
        receipts.append({'mode': mode, 'case': case, 'command': command,
                         'log_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                         'measured_log_lines': len(measured.splitlines())})
        print(mode, case, 'measured log lines:', len(measured.splitlines()), flush=True)
(OUT / 'receipts.json').write_text(json.dumps(receipts, indent=2))
