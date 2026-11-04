"""Configure/build the open-source static ArkTS runtime.

Supported hosts: native macOS ARM64 (the recorded port) and Linux x86_64,
which also covers Windows via WSL2 (see README "Windows (WSL2)").
"""
import os
import pathlib
import platform
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
(ROOT / 'build').mkdir(exist_ok=True)
lock = (ROOT / 'build/source-build.lock').open('a')
try:
    import fcntl
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
except ImportError:
    raise SystemExit('Native Windows is not supported; build inside WSL2 (see README).')

HOST = (platform.system(), platform.machine())
TOOLCHAINS = {
    ('Darwin', 'arm64'): 'native/macos-arm64.cmake',
    ('Linux', 'x86_64'): 'native/linux-x86_64.cmake',
}
if HOST not in TOOLCHAINS:
    raise SystemExit(f'Unsupported host {HOST}; supported: {sorted(TOOLCHAINS)}')

subprocess.run([sys.executable, str(ROOT / 'bootstrap_deps.py'), '--verify'], check=True)
environment = os.environ.copy()
environment['VENV_DIR'] = str(ROOT / 'build/venv')
extra_path = [str(ROOT / 'build/venv/bin')]
if HOST[0] == 'Darwin':
    extra_path.append('/opt/homebrew/opt/ruby/bin')
environment['PATH'] = os.pathsep.join(extra_path + [environment['PATH']])
config = ['cmake', '-S', str(ROOT / 'vendor/runtime_core/static_core'),
          '-B', str(ROOT / 'build/ark-source'), '-G', 'Ninja',
          '-DCMAKE_TOOLCHAIN_FILE=' + str(ROOT / TOOLCHAINS[HOST]),
          '-DCMAKE_BUILD_TYPE=Release', '-DPANDA_WITH_TESTS=OFF',
          '-DPANDA_WITH_BENCHMARKS=OFF',
          '-DES2PANDA_PATH=' + str(ROOT / 'vendor/ets_frontend/ets2panda')]
default_jobs = 6 if HOST[0] == 'Darwin' else max(1, (os.cpu_count() or 6) - 2)
jobs = os.environ.get('ARK_BUILD_JOBS', str(default_jobs))
if '--resume' not in sys.argv:
    with (ROOT / 'build/configure.log').open('w') as log:
        result = subprocess.run(config, env=environment, stdout=log, stderr=log)
    print('configure:', result.returncode, flush=True)
    if result.returncode:
        print((ROOT / 'build/configure.log').read_text()[-8000:])
        raise SystemExit(result.returncode)
if '--configure-only' not in sys.argv:
    compiler_only = '--compiler-only' in sys.argv
    log_path = ROOT / ('build/compiler-build.log' if compiler_only
                       else 'build/source-build.log')
    targets = (['es2panda_stdlib_compiler'] if compiler_only else
               ['ark'] if '--runtime-only' in sys.argv else ['ark', 'es2panda_stdlib_compiler'])
    with log_path.open('w') as log:
        result = subprocess.run(['cmake', '--build', str(ROOT / 'build/ark-source'),
                                 '--target', *targets,
                                 '--parallel', jobs], env=environment,
                                stdout=log, stderr=log)
    print('build:', result.returncode, flush=True)
    if result.returncode:
        lines = log_path.read_text(errors='replace').replace('\0', '').splitlines()
        selected = set()
        for index, line in enumerate(lines):
            if ('FAILED:' in line or 'error:' in line or 'Undefined symbols' in line or
                    'undefined reference' in line or
                    'FATAL' in line or 'Assertion failed' in line):
                selected.update(range(index, min(len(lines), index + 12)))
        if selected:
            print('\n'.join(lines[index][:500] for index in sorted(selected))[-7000:])
        else:
            print('\n'.join(lines[-15:])[-3000:])
    raise SystemExit(result.returncode)
