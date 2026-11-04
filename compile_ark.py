"""Compile static ArkTS stdlib + benchmark with the native bootstrap frontend."""
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent
(ROOT / 'build').mkdir(exist_ok=True)
COMPILER = ROOT / 'build/ark-source/bin/es2panda_stdlib_compiler'
STDLIB = ROOT / 'vendor/runtime_core/static_core/plugins/ets/stdlib'
commands = [
    ('compile-stdlib', [str(COMPILER), '--opt-level=2', '--thread=0',
        '--extension=ets',
        '--output=' + str(ROOT / 'build/ark-source/plugins/ets/etsstdlib.abc'),
        '--gen-stdlib=true', '--emit-metadata',
        '--arktsconfig=' + str(STDLIB / 'stdconfig.json')]),
    ('compile-suite', [str(COMPILER), '--extension=ets', '--opt-level=2',
        '--output=' + str(ROOT / 'build/suite.abc'), str(ROOT / 'bench/suite.ets')]),
]
for name, command in commands:
    with (ROOT / 'build' / (name + '.log')).open('w') as log:
        result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=log)
    print(name, result.returncode, flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)
