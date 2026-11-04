#!/bin/sh
# Reproduce the recorded source port without installing system packages.
set -eu
cd "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
if [ "$(uname -s)" != Darwin ] || [ "$(uname -m)" != arm64 ]; then
    echo 'This port is validated only on native macOS ARM64.' >&2
    exit 1
fi
for executable in python3 git cmake clang clang++ ruby otool; do
    command -v "$executable" >/dev/null || {
        echo "Missing prerequisite: $executable (see README.md)" >&2
        exit 1
    }
done
python3 -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ required"'
mkdir -p build results
if [ ! -x build/venv/bin/python ]; then
    python3 -m venv build/venv
fi
build/venv/bin/python -m pip install -r native/build-requirements.txt
python3 bootstrap_deps.py
python3 build_source.py
python3 compile_ark.py
python3 verify_runtime.py
python3 native/verify_port.py
printf '%s\n' 'Native macOS ArkTS build and focused validation completed.'
