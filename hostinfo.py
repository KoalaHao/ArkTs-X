"""Host-specific details shared by the benchmark runners (macOS ARM64, Linux/WSL2)."""
import pathlib
import platform
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent
DARWIN = platform.system() == 'Darwin'
LIB_SUFFIX = '.dylib' if DARWIN else '.so'
TOOLCHAIN = 'native/macos-arm64.cmake' if DARWIN else 'native/linux-x86_64.cmake'
# Linux x86_64 keeps upstream's default 32-bit managed pointers; the Mac port forces 64.
MANAGED_POINTER_BITS = 64 if DARWIN else 32
# BSD time reports bytes with -l; GNU time reports KiB with -v.
TIME_PREFIX = ['/usr/bin/time', '-l'] if DARWIN else ['/usr/bin/time', '-v']


def cpu_name():
    if DARWIN:
        return subprocess.check_output(['sysctl', '-n', 'machdep.cpu.brand_string'], text=True).strip()
    for line in pathlib.Path('/proc/cpuinfo').read_text().splitlines():
        if line.startswith('model name'):
            return line.split(':', 1)[1].strip()
    return platform.processor()


def is_wsl():
    try:
        return 'microsoft' in pathlib.Path('/proc/version').read_text().lower()
    except OSError:
        return False


def peak_rss_bytes(stderr_text):
    if DARWIN:
        match = re.search(r'(\d+)\s+maximum resident set size', stderr_text)
        return int(match[1]) if match else None
    match = re.search(r'Maximum resident set size \(kbytes\):\s*(\d+)', stderr_text)
    return int(match[1]) * 1024 if match else None


def runtime_libs():
    return [ROOT / 'build/ark-source/lib' / ('lib' + name + LIB_SUFFIX) for name in (
        'arkruntime', 'arkbase', 'arkaotmanager', 'arktarget_options')]
