"""Run the focused LLDB JIT-install/execution check, outside benchmark timing."""
import os
import pathlib
import shlex
import signal
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
arguments = [
    '--load-runtimes=ets',
    '--boot-panda-files=' + str(ROOT / 'build/ark-source/plugins/ets/etsstdlib.abc'),
    '--interpreter-type=cpp', '--compiler-enable-jit=true',
    '--compiler-enable-osr=false', '--no-async-jit=true',
    '--compiler-hotness-threshold=0', '--compiler-profiling-threshold=0',
    '--compiler-regex=.*numeric.*',
    str(ROOT / 'build/port_smoke.abc'), 'port_smoke.ETSGLOBAL::main',
]
proof_command = 'jit-proof'
log_path = ROOT / 'results/jit-entry-proof.txt'
expected_markers = ['JIT_INSTALL_OBSERVED', 'JIT_EXECUTION_PROVED']
if '--osr' in sys.argv:
    arguments = [
        '--load-runtimes=ets',
        '--boot-panda-files=' + str(ROOT / 'build/ark-source/plugins/ets/etsstdlib.abc'),
        '--interpreter-type=cpp', '--compiler-enable-jit=true',
        '--compiler-enable-osr=true', '--compiler-hotness-threshold=100',
        '--compiler-profiling-threshold=50', '--compiler-regex=.*spin.*',
        str(ROOT / 'build/osr_smoke.abc'), 'osr_smoke.ETSGLOBAL::main',
    ]
    proof_command = 'osr-proof'
    log_path = ROOT / 'results/osr-entry-proof.txt'
    expected_markers = ['OSR_PREPARE_OBSERVED', 'OSR_STATE_RECONSTRUCTED', 'OSR_EXECUTION_PROVED']
command = ['lldb', '--batch', str(ROOT / 'build/ark-source/bin/ark'),
           '-o', 'settings set target.disable-aslr false',
           '-o', 'settings set -- target.run-args ' + shlex.join(arguments),
           '-o', 'command script import ' + str(ROOT / 'native/jit_proof.py'),
           '-o', proof_command]
with log_path.open('w') as log:
    process = subprocess.Popen(command, stdout=log, stderr=log, cwd=ROOT, start_new_session=True)
    try:
        code = process.wait(timeout=45)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait()
        raise SystemExit('JIT debugger proof timed out; see ' + str(log_path))
output = log_path.read_text()
print(output)
if code or any(marker not in output for marker in expected_markers):
    raise SystemExit('JIT debugger proof did not pass')
