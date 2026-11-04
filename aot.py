"""Ahead-of-time (ark_aot / paoc) compilation helpers. Linux x86_64 (incl. WSL2) only.

The Mac port does not support native Ark AOT (.an output/loading is unported).
`python3 aot.py [file.abc ...]` AOT-compiles the boot stdlib plus the given
bytecode files into build/aot/*.an.
"""
import pathlib
import subprocess
import sys

import hostinfo

ROOT = pathlib.Path(__file__).resolve().parent
BIN = ROOT / 'build/ark-source/bin'
ARK_AOT = BIN / 'ark_aot'
STDLIB = ROOT / 'build/ark-source/plugins/ets/etsstdlib.abc'
OUT = ROOT / 'build/aot'
STDLIB_AN = OUT / 'etsstdlib.an'


def supported():
    return not hostinfo.DARWIN and ARK_AOT.exists()


def an_path(abc):
    return OUT / (pathlib.Path(abc).stem + '.an')


def _run(command, log_name):
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / log_name).open('w') as log:
        result = subprocess.run(command, cwd=ROOT, stdout=log, stderr=log)
    if result.returncode:
        raise SystemExit(f'ark_aot failed ({result.returncode}); see {OUT / log_name}')


def compile_stdlib():
    """Boot-image AOT of the standard library (reused while etsstdlib.abc is unchanged)."""
    if STDLIB_AN.exists() and STDLIB_AN.stat().st_mtime >= STDLIB.stat().st_mtime:
        return STDLIB_AN
    _run([str(ARK_AOT), '--load-runtimes=ets', '--boot-panda-files=' + str(STDLIB),
          '--paoc-panda-files=' + str(STDLIB), '--paoc-boot-output=' + str(STDLIB_AN)],
         'etsstdlib.log')
    return STDLIB_AN


def compile_app(abc):
    out = an_path(abc)
    _run([str(ARK_AOT), '--load-runtimes=ets', '--boot-panda-files=' + str(STDLIB),
          '--paoc-panda-files=' + str(abc), '--paoc-output=' + str(out)],
         out.stem + '.log')
    return out


def run_options(abc):
    """Options for `ark` to execute AOT code for the stdlib and `abc`, with JIT disabled."""
    files = [compile_stdlib(), compile_app(abc)]
    return ['--aot-files=' + ':'.join(str(path) for path in files),
            '--compiler-enable-jit=false']


if __name__ == '__main__':
    if not supported():
        raise SystemExit('AOT needs build/ark-source/bin/ark_aot on Linux x86_64 (see README).')
    print(compile_stdlib())
    for path in sys.argv[1:]:
        print(compile_app(ROOT / path))
