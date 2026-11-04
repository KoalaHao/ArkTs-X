#!/bin/sh
# Build the static ArkTS runtime on Linux x86_64 (including WSL2 on Windows).
# Run from a checkout on the Linux filesystem (not /mnt/c): it is much faster
# and keeps patch files byte-exact.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ "$(uname -s)" != Linux ] || [ "$(uname -m)" != x86_64 ]; then
    echo 'build_linux.sh supports Linux x86_64 only.' >&2
    exit 1
fi
case "$(pwd)" in
    /mnt/[a-z]/*) echo 'Clone into the WSL filesystem (e.g. ~/ArkTs-X), not /mnt/<drive>.' >&2; exit 1;;
esac
# Debian/Ubuntu: sudo apt-get install -y git cmake ninja-build clang ruby \
#   python3-venv wget xz-utils unzip time file
for executable in python3 git cmake clang clang++ ruby wget xz unzip; do
    command -v "$executable" >/dev/null || {
        echo "Missing prerequisite: $executable (see README.md, Windows/Linux section)" >&2
        exit 1
    }
done
[ -x /usr/bin/time ] || { echo 'Missing prerequisite: GNU time (/usr/bin/time)' >&2; exit 1; }
python3 -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ required"'
mkdir -p build results
if [ ! -x build/venv/bin/python ]; then
    python3 -m venv build/venv
fi
build/venv/bin/python -m pip install -q -r native/build-requirements.txt
python3 bootstrap_deps.py
python3 build_source.py
python3 compile_ark.py
python3 verify_runtime.py
printf '%s\n' 'Linux x86_64 ArkTS build and focused validation completed.'
