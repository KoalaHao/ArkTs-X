"""Check native Ark runtime behavior before collecting benchmark timings."""
import json
import math
import pathlib
import subprocess

import aot

ROOT = pathlib.Path(__file__).resolve().parent
(ROOT / 'results').mkdir(exist_ok=True)
ARK = ROOT / 'build/ark-source/bin/ark'
COMPILER = ROOT / 'build/ark-source/bin/es2panda_stdlib_compiler'
STDLIB = ROOT / 'build/ark-source/plugins/ets/etsstdlib.abc'

subprocess.run([str(COMPILER), '--extension=ets', '--opt-level=2',
                '--output=' + str(ROOT / 'build/port_smoke.abc'),
                str(ROOT / 'bench/port_smoke.ets')], cwd=ROOT, check=True)

expected_number = 0.0
expected_objects = 0
for i in range(10000):
    seed = i % 17
    value = float(seed)
    for j in range(64):
        value = value * .999 + j * .125
    expected_number += value
    expected_objects += 101 * seed + 4950

modes = {
    'cpp-interpreter': ['--interpreter-type=cpp', '--compiler-enable-jit=false'],
    'irtoc-interpreter': ['--interpreter-type=irtoc', '--compiler-enable-jit=false'],
    'normal-jit': ['--interpreter-type=cpp', '--compiler-enable-jit=true',
                   '--compiler-enable-osr=false'],
    'jit-osr': ['--interpreter-type=irtoc', '--compiler-enable-jit=true',
                '--compiler-enable-osr=true'],
    'gc-stress': ['--interpreter-type=irtoc', '--compiler-enable-jit=true',
                  '--init-heap-size-limit=16777216', '--heap-size-limit=33554432',
                  '--heap-verifier=pre:post:fail_on_verification',
                  '--log-info=gc',
                  '--log-detailed-gc-info-enabled=true'],
}
if aot.supported():
    # Pure AOT: stdlib + program compiled by ark_aot, JIT off; plus AOT under GC stress.
    aot_options = aot.run_options(ROOT / 'build/port_smoke.abc')
    modes['aot'] = [*aot_options]
    modes['aot-gc-stress'] = [*aot_options, *modes['gc-stress'][2:]]
receipts = []
for name, options in modes.items():
    command = [str(ARK), '--load-runtimes=ets', '--boot-panda-files=' + str(STDLIB),
               *options, str(ROOT / 'build/port_smoke.abc'), 'port_smoke.ETSGLOBAL::main']
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=180)
    (ROOT / 'results' / f'port-{name}.stdout').write_text(process.stdout)
    (ROOT / 'results' / f'port-{name}.stderr').write_text(process.stderr)
    if process.returncode:
        raise SystemExit(f'{name} failed ({process.returncode}): {process.stderr[-3000:]}')
    lines = [line.split() for line in process.stdout.splitlines() if line.startswith('PORT_SMOKE ')]
    if len(lines) != 1:
        raise SystemExit(f'{name}: missing or duplicate smoke result: {process.stdout}')
    _, number, objects, caught, remaining = lines[0]
    if not math.isclose(float(number), expected_number, rel_tol=1e-10, abs_tol=1e-8):
        raise SystemExit(f'{name}: numeric mismatch: {number} != {expected_number}')
    if [int(objects), int(caught), int(remaining)] != [expected_objects, 1, 113]:
        raise SystemExit(f'{name}: object/exception mismatch: {lines[0]}')
    gc = [line.split() for line in process.stdout.splitlines() if line.startswith('PORT_GC ')]
    if len(gc) != 1 or [int(gc[0][1]), int(gc[0][2])] != [4, 123] or int(gc[0][3]) <= 0:
        raise SystemExit(f'{name}: missing completed GC/live-reference proof: {gc}')
    receipts.append({'mode': name, 'command': command, 'output': ' '.join(lines[0]),
                     'gc': ' '.join(gc[0])})
    (ROOT / 'results/native-runtime-validation.json').write_text(json.dumps(receipts, indent=2))
    print(name, 'passed:', ' '.join(lines[0]), flush=True)

print('All execution-mode checksums passed. JIT-entry proof is a separate debugger check.')
