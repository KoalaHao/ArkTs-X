# Recovery-kit validation — 2026-11-04

Validated locally on an Apple M1 Max, native ARM64, macOS 26.6.2 (25G83),
Apple Clang 21.0.0, CMake 4.2.3, Python 3.11.5, and Ruby 4.0.2.
Exact Python package versions are recorded in `native/build-requirements.txt`.

## Source recovery

- Initialized a separate kit directory with no previous CMake build or venv.
- Recovered all 15 pinned Git checkouts using the original experiment's local
  Git object cache. These are independent checkouts with no Git alternates or
  symlinks to the original source trees.
- Subsequently fetched every pinned commit from its actual GitHub origin,
  confirming all 15 pins remain remotely retrievable.
- Applied and verified all three patches, including the new Mach-O writer.
  Runtime, frontend and VIXL patches exactly match the original patched sources.
- Five recovery-guard unit tests passed: exact/idempotent patch verification,
  extra edits, changes to a newly added file, unexpected untracked source, and
  a missing added file. Verification preserves the real Git index.

## Native build and execution

- `python3 build_source.py`: clean configure and all 1,973 Ninja steps passed;
  built native `ark` and `es2panda_stdlib_compiler`.
- `./build_macos.sh`: end-to-end rerun passed, including dependency/patch
  verification, incremental native build, stdlib and benchmark compilation,
  runtime smoke tests, and ABI probes.
- All five runtime modes passed independent numeric/object/exception checks:
  C++ interpreter, IRtoC interpreter, normal JIT, JIT/OSR, and GC stress with
  32 MiB heap plus pre/post heap verification. Each also checked four completed
  explicit collections and a live reference.
- Mach-O branch relocation/linking, 1,000 fiber switches, executable-memory
  publication, native integer aliases, and x18 exclusion from generated IRtoC
  objects passed.
- The README's native hello-world compile/run example printed
  `ARK_SMOKE_OK 42`.
- The launcher and bootstrap frontend identify as Mach-O ARM64 executables.
- Shell syntax, Python compilation, staged whitespace, and credential-pattern
  checks passed. Build outputs, downloaded sources, venvs and proprietary SDK
  probes are excluded from Git.

Receipts: [`evidence/recovery/`](evidence/recovery/), including clean-build task
lines, configure output, wrapper validation, source pins, toolchain versions,
runtime checks and fresh artifact fingerprints. Compiled binaries are not
committed.

## Boundaries

The game/microbenchmark results and LLDB JIT/OSR proofs elsewhere in `evidence/`
are from the original experiment and were preserved without rerunning the full
performance suite during packaging. Their hashes refer to the original inputs.

The combined game-suite GC crash is unresolved. Native AOT, Windows, Linux and
Intel macOS execution were not validated by this packaging run. The full
upstream test suite was not run. Focused passes do not establish production
readiness or remove any limitation in the README and game report.
