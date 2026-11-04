"""Run native ABI probes and inspect source-built IRtoC machine code."""
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = 'vendor/runtime_core/static_core'

def run(*args):
    subprocess.run(args, cwd=ROOT, check=True)

common = ['clang++', '-std=c++17', '-Wall', '-Wextra', '-Werror']
run(*common, '-I', SRC, 'native/test_macos_assembly.cpp', '-o', 'build/test_macos_assembly')
run('./build/test_macos_assembly', 'build/test_macos.S')
run('clang', '-arch', 'arm64', '-x', 'assembler', '-c', 'build/test_macos.S', '-o', 'build/test_macos.o')
run(*common, 'native/test_macos_link.cpp', 'build/test_macos.o', '-o', 'build/test_macos_link')
run('./build/test_macos_link')
run(*common, '-O2', '-DPANDA_TARGET_MACOS', '-DPANDA_TARGET_ARM64',
    '-I', SRC, '-I', 'build/ark-source/runtime/include',
    'native/test_macos_fibers.cpp',
    *[f'{SRC}/runtime/fibers/arch/aarch64/{name}.S' for name in ('get', 'update', 'switch')],
    '-o', 'build/test_macos_fibers')
run('./build/test_macos_fibers')
run(*common, 'native/test_macos_execmem.cpp', '-o', 'build/test_macos_execmem')
run('./build/test_macos_execmem')
run(*common, '-DNDEBUG', '-DPANDA_TARGET_MACOS', '-DPANDA_TARGET_UNIX',
    '-DPANDA_TARGET_ARM64', '-DPANDA_TARGET_64',
    '-Wno-error=deprecated-literal-operator', '-Wno-error=unnecessary-virtual-specifier',
    '-I', SRC, '-I', SRC + '/compiler', '-I', 'build/ark-source',
    '-I', 'build/ark-source/compiler/generated',
    '-I', SRC + '/third_party/utils_native/base/include',
    'native/test_macos_integer_types.cpp', '-o', 'build/test_macos_integer_types')
run('./build/test_macos_integer_types')
print('Native intptr_t/uintptr_t/size_t immediates passed; unsupported types stay rejected')

for name in ('irtoc_interpreter', 'irtoc_fastpath', 'irtoc_ets_fastpath'):
    obj = ROOT / 'build/ark-source/irtoc' / name / (name + '.o')
    identity = subprocess.check_output(['file', str(obj)], text=True).strip()
    if 'Mach-O 64-bit object arm64' not in identity:
        raise SystemExit(f'Unexpected object format: {identity}')
    assembly = subprocess.check_output(['otool', '-tv', str(obj)], text=True)
    if re.search(r'\b[wx]18\b', assembly):
        raise SystemExit(f'Reserved Darwin register appears in {obj}')
    print(f'{name}: native arm64 object, no x18/w18 instructions')

print('Native ABI probes passed. Runtime/JIT execution needs separate validation.')
