# ArkTs-X

**X for cross-platform. Currently validated: experimental native macOS ARM64.**

A reproducible **source port kit** for OpenHarmony's static ArkTS runtime
(**ArkTS-Sta / ETS**) on native macOS ARM64. It preserves the macOS patches,
exact upstream commits, build tools, native regression probes, and Dart/ArkTS
benchmark evidence from the original experiment.

`bootstrap_deps.py` downloads the pinned open-source runtime, frontend, and
third-party sources into `vendor/`, then applies the complete macOS patches.
The upstream source trees and compiled binaries are not stored in this Git
repository. No DevEco SDK or proprietary Huawei binary is required.

> **Experimental:** isolated benchmarks and focused interpreter/JIT/OSR checks
> pass, but running all game workloads sequentially in one process reproduces
> an unresolved GC root-scan crash. Native Ark AOT is not ported/validated.
> Do not treat this as a production-ready runtime or an ArkUI port.

## Platform scope

The goal is a reproducible standalone ArkTS compiler/runtime that can grow
across desktop platforms. This repository currently provides the macOS ARM64
recovery/build path; the name is a direction, not a claim of tested support.

| Platform | Upstream situation | Status in ArkTs-X |
|---|---|---|
| macOS ARM64 | Upstream has macOS host tooling/platform code | Native static runtime, interpreter, JIT/OSR and focused tests work experimentally; combined GC fault remains |
| Linux | Upstream documents Ubuntu development, native runtime execution and ARM cross-compilation | Existing upstream platform; no Linux recipe or validation added here yet |
| Windows (WSL2) | Linux x86_64 runtime running under WSL2 | Builds unmodified; both interpreters, JIT, OSR and GC-stress validation pass; benchmarks complete with checksums (see [WINDOWS_REPORT.md](WINDOWS_REPORT.md)) |
| Windows (native Win32) | Upstream has Windows host-tool targets and a MinGW toolchain configuration | Full standalone runtime/JIT is not ported; use WSL2 |
| macOS x86_64 | Not exercised in this experiment | Unvalidated |

See the upstream [static runtime development guide](https://github.com/openharmony/arkcompiler_runtime_core/blob/master/static_core/README.md)
and [host-tool build targets](https://github.com/openharmony/arkcompiler_runtime_core#building).
A host compiler/preview tool being available does not establish that the entire
standalone static runtime, JIT, AOT and standard library work on that platform.
ArkTS is not exclusive to HarmonyOS; Linux support already exists upstream.

### Why was macOS work needed if upstream lists a Mac target?

Host tools and a complete standalone execution runtime have different coverage.
At our pinned runtime revision, [`compile_method.cpp`](https://github.com/openharmony/arkcompiler_runtime_core/blob/6b3a0de5e971b667a1e46e17283595df67a99f0b/static_core/compiler/compile_method.cpp#L329-L339)
explicitly rejects compilation on Apple platforms, and
[compiler CMake](https://github.com/openharmony/arkcompiler_runtime_core/blob/6b3a0de5e971b667a1e46e17283595df67a99f0b/static_core/compiler/CMakeLists.txt#L257)
excludes code-generation sources on macOS. The IRtoC generator emits ELF objects;
this port adds a Mach-O path and Darwin ARM64 ABI accommodations. Existing
macOS platform code and host-tool targets are useful foundations, but do not
establish support for this runtime's JIT/OSR execution path.

## Build and verify

Requirements:

- An Apple Silicon Mac; only an M1 Max running macOS 26.6.2 was validated.
- Xcode command-line tools (`clang`, `otool`, and optionally `lldb`).
- Git, Python 3.10+, CMake, and a recent Ruby on `PATH`.
  The recorded build used CMake 4.2.3, Apple Clang 21 and Homebrew Ruby 4.0.2.
  The macOS system Ruby is not the tested toolchain. The build script also
  looks for Ruby at `/opt/homebrew/opt/ruby/bin`.
- Internet access for GitHub source downloads and the pinned Python packages.
- Several GB of free disk space for the source checkouts and native build.
  Dart is optional and is only needed to run comparison benchmarks.

```sh
git clone https://github.com/KoalaHao/ArkTs-X.git
cd ArkTs-X
./build_macos.sh
```

The script creates `build/venv`, installs `native/build-requirements.txt`,
fetches and verifies the pinned sources, builds the native runtime and bootstrap
frontend, compiles the standard library, and runs the runtime and native ABI
checks. It does not install system packages or change system settings.

Equivalent individual steps:

```sh
python3 -m venv build/venv
build/venv/bin/python -m pip install -r native/build-requirements.txt
python3 bootstrap_deps.py
python3 build_source.py
python3 compile_ark.py
python3 verify_runtime.py
python3 native/verify_port.py
```

`build_source.py` defaults to the supported `ark` and
`es2panda_stdlib_compiler` targets. It deliberately excludes native AOT.
It locks its build directory to prevent two builds corrupting Ninja's state.
To resume after interruption: `python3 build_source.py --resume`.
`--runtime-only` and `--compiler-only` are available for incremental work.

Outputs:

- `build/ark-source/bin/ark`: native Mach-O ARM64 launcher.
- `build/ark-source/bin/es2panda_stdlib_compiler`: native source-to-ABC compiler.
- `build/ark-source/plugins/ets/etsstdlib.abc`: compiled standard library.
- `build/ark-source/lib/`: runtime libraries; retain this build layout.
- `build/source-receipt.json`: source commit IDs and patch fingerprints.
- `results/`: new validation/benchmark receipts (ignored by Git).

For example:

```sh
build/ark-source/bin/es2panda_stdlib_compiler \
  --extension=ets --opt-level=2 --output=build/hello.abc bench/native_hello.ets
build/ark-source/bin/ark --load-runtimes=ets \
  --boot-panda-files=build/ark-source/plugins/ets/etsstdlib.abc \
  build/hello.abc native_hello.ETSGLOBAL::main
```

### Windows (WSL2) and Linux x86_64

The static runtime's execution engine (signals, `mmap`, fibers, futexes, JIT
code publication) targets Unix, so on Windows it runs as the Linux x86_64
build inside WSL2. Linux x86_64 is an upstream platform, so the pinned sources
build without extra runtime patches. The Mac patches are guarded by
`__APPLE__`/`PANDA_TARGET_MACOS` and have no effect there. The kit adds
`native/linux-x86_64.cmake`, pins the x86_64 JIT backend dependencies
(asmjit, zydis, with upstream's own patches), and makes the runners portable
(`hostinfo.py`: GNU `time -v`, `/proc/cpuinfo`, `.so` names).

From PowerShell (WSL2 with Debian or Ubuntu installed):

```powershell
powershell -ExecutionPolicy Bypass -File build_windows.ps1 -InstallPackages -Bench
```

This copies the kit into `~/ArkTs-X` inside WSL, which avoids slow `/mnt/c`
builds and CRLF-converted patches, then runs `build_linux.sh`. To do the same
by hand inside WSL or on Linux:

```sh
sudo apt-get install -y git cmake ninja-build clang ruby python3-venv wget xz-utils unzip time file rsync
git clone https://github.com/KoalaHao/ArkTs-X.git ~/ArkTs-X && cd ~/ArkTs-X
sh build_linux.sh
dart compile exe bench/suite.dart -o build/dart_aot   # optional, for benchmarks
python3 run_bench.py --runs 5
python3 run_game_bench.py --runs 3
```

Validated on Windows 11 (26200), WSL2 Debian 13, clang 19.1.7, Intel i5-13600KF.
The Linux configure downloads Node.js v18.13 headers (upstream's
`install-third-party --node`) for the frontend's N-API bindings. Linux keeps
upstream's default 32-bit managed pointers.

The bootstrap is idempotent and checks every pinned commit plus the complete
patched source contents. It refuses to reset or overwrite a different revision
or unexpected edits. `python3 bootstrap_deps.py --verify` is offline and makes
no source changes. To experiment with runtime code, keep those changes in a
separate checkout; this recovery kit intentionally verifies the recorded port.
If a download fails before checkout, remove only that incomplete dependency
checkout before retrying. Existing successful checkouts are reused.

## What the port changes

See [native/PORTING.md](native/PORTING.md) for the technical explanation.
The patches handle Mach-O IRtoC objects and relocations, Darwin's reserved x18,
OSR bridges, native integer typedefs, shared runtime state, CPU features, POSIX
sources, ICU initialization, and macOS build-generator/compiler differences.
The toolchain uses the existing 64-bit managed-pointer configuration.

- [native/macos-port.patch](native/macos-port.patch): runtime source changes,
  including the new Mach-O assembly writer.
- [native/frontend-appleclang.patch](native/frontend-appleclang.patch): frontend
  Apple Clang warning accommodation.
- [native/vixl-macos.patch](native/vixl-macos.patch): VIXL warning accommodation.
- [source-revisions.json](source-revisions.json): immutable source pins.
- [patch-sha256.json](patch-sha256.json): patch integrity fingerprints.

No GC algorithm, heap/object layout, bytecode format, or stack-map algorithm
was replaced. Existing validation and unsupported-operation diagnostics remain.

## Validation and benchmark evidence

`verify_runtime.py` checks both interpreters, normal JIT, JIT/OSR, and a 32 MiB
heap with pre/post heap verification, against independent reference values.
`native/verify_port.py` tests Mach-O linking, fiber switching, executable memory,
Darwin integer aliases, and x18 exclusion from generated IRtoC objects.

Optional debugger checks (outside benchmark timing):

```sh
python3 native/run_jit_proof.py
build/ark-source/bin/es2panda_stdlib_compiler --extension=ets --opt-level=2 \
  --output=build/osr_smoke.abc bench/osr_smoke.ets
python3 native/run_jit_proof.py --osr
```

Dart comparisons require a native Dart SDK; the historical run used Dart 3.13.3:

```sh
dart compile exe bench/suite.dart -o build/dart_aot
python3 run_bench.py --runs 3
python3 run_game_bench.py --runs 3
python3 probe_game_gc.py
```

See [REPORT.md](REPORT.md) for microbenchmarks and
[GAME_REPORT.md](GAME_REPORT.md) for game CPU workloads, memory and GC findings.
Historical raw receipts are archived under [evidence/](evidence/), including the
combined-workload failure. They describe the original experiment; reruns write
to `results/` and may differ. These are CPU tests, not GPU/rendering FPS tests.

The recovery guards can be checked independently with
`python3 -m unittest -v test_bootstrap`. See [VALIDATION.md](VALIDATION.md) for
checks performed when packaging this repository.

## Known limits

- Combined game workloads can crash in G1 GC root scanning. All 54 historical
  case-isolated game runs passed; that does not resolve the combined failure.
- Native Ark AOT `.an` output/loading and JIT debug-image emission remain
  unported or unvalidated. Working JIT does not establish AOT support.
- The full upstream test suite has not been run.
- Windows is supported only through WSL2 (Linux x86_64 build); native Win32
  execution is not ported. Intel Macs, older macOS releases and other HarmonyOS
  runtime variants are not validated. Do not infer support from build target defaults.
- This does not supply ArkUI, a desktop widget toolkit, or HarmonyOS APIs.

## Upstream and licensing

Based on [OpenHarmony ArkCompiler Runtime Core](https://github.com/openharmony/arkcompiler_runtime_core)
and [ETS Frontend](https://github.com/openharmony/arkcompiler_ets_frontend).
All source pins are recorded rather than following moving branches.

This kit is Apache-2.0; see [LICENSE](LICENSE) and [NOTICE](NOTICE).
Downloaded upstream and third-party code retains its own license and notices.
This is an independent experimental port, with no upstream endorsement.
