"""Configure/build the open-source static ArkTS runtime on Apple Silicon."""
import os
import fcntl
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
(ROOT / 'build').mkdir(exist_ok=True)
lock = (ROOT / 'build/source-build.lock').open('a')
fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
subprocess.run([sys.executable, str(ROOT / 'bootstrap_deps.py'), '--verify'], check=True)
environment = os.environ.copy()
environment['VENV_DIR'] = str(ROOT / 'build/venv')
environment['PATH'] = (str(ROOT / 'build/venv/bin') +
                       ':/opt/homebrew/opt/ruby/bin:' + environment['PATH'])
config = ['cmake', '-S', str(ROOT / 'vendor/runtime_core/static_core'),
          '-B', str(ROOT / 'build/ark-source'), '-G', 'Ninja',
          '-DCMAKE_TOOLCHAIN_FILE=' + str(ROOT / 'native/macos-arm64.cmake'),
          '-DCMAKE_BUILD_TYPE=Release', '-DPANDA_WITH_TESTS=OFF',
          '-DPANDA_WITH_BENCHMARKS=OFF',
          '-DES2PANDA_PATH=' + str(ROOT / 'vendor/ets_frontend/ets2panda')]
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
                                 '--parallel', '6'], env=environment,
                                stdout=log, stderr=log)
    print('build:', result.returncode, flush=True)
    if result.returncode:
        lines = log_path.read_text(errors='replace').replace('\0', '').splitlines()
        selected = set()
        for index, line in enumerate(lines):
            if ('FAILED:' in line or 'error:' in line or 'Undefined symbols' in line or
                    'FATAL' in line or 'Assertion failed' in line):
                selected.update(range(index, min(len(lines), index + 12)))
        if selected:
            print('\n'.join(lines[index][:500] for index in sorted(selected))[-7000:])
        else:
            print('\n'.join(lines[-15:])[-3000:])
    raise SystemExit(result.returncode)
