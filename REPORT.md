# Native macOS ArkTS / Dart benchmark

Follow-up: the game-framework suite in [GAME_REPORT.md](GAME_REPORT.md) passes
54 isolated runs but exposes a reproducible GC root-scan fault when multiple
workloads run sequentially in this experimental ArkTS build. The microbenchmark
results below remain narrow workload measurements, not proof of whole-engine stability.

**The source-built native ARM64 ArkTS static runtime now runs both interpreters,
normal JIT, and OSR on this Mac. The paired benchmarks complete with all checksums
passing. The results are mixed; there is no overall speed winner.**

## Timings

Median of three fresh-process medians, milliseconds per workload operation;
lower is better. Each process warms each workload for at least one second and
records five calibrated batch samples. Both JIT modes start from precompiled
input: Dart kernel IR (`.dill`) and Ark bytecode (`.abc`). Source frontend
compilation is outside the timed processes.

| Workload | Dart kernel JIT | Dart AOT | ArkTS JIT/OSR |
|---|---:|---:|---:|
| sieve | 0.5195 ms | 0.4805 ms | 0.3574 ms |
| vectors | 0.5664 ms | 0.4961 ms | 1.1250 ms |
| objects | 0.1250 ms | 0.1348 ms | 0.1807 ms |
| text | 1.0156 ms | 0.9609 ms | 0.5742 ms |

ArkTS is faster on this sieve and text workload. Dart is faster on the float64
buffer and object workloads. These are small standalone implementations, not
Crux, Pyxis, rendering, UI, networking, or LLM benchmarks. ArkTS loop/index
integers are 32-bit; native Dart uses its normal `int`. See README for the exact
workload sizes and algorithm matching.

## Peak memory

The process-wide peak RSS includes startup, JIT compilation where applicable,
and all four workloads. It is not idle memory or a measurement of only the VM.

| Mode | Median peak RSS | Range across 3 processes |
|---|---:|---:|
| Dart kernel JIT | 84.92 MiB | 84.47–85.48 MiB |
| Dart AOT | 50.88 MiB | 50.80–51.36 MiB |
| ArkTS JIT/OSR | 34.22 MiB | 34.14–34.42 MiB |

The source-launch Dart JIT baseline peaked near 194 MiB because it included
source frontend compilation; that is not used in this primary comparison.
`evidence/source-launch-results.json` retains that separate launch-mode result.
Default heap/GC policies differ, and Ark uses the existing 64-bit managed-pointer
build configuration. Do not generalize these peaks to all Dart/ArkTS apps or
attribute their difference to the programming languages alone.

## Verified native execution

- `ark` and `libarkruntime.dylib` are native Mach-O ARM64 artifacts built from the
  pinned open-source repositories, with the local patches supplied here.
- C++ interpreter, IRtoC interpreter, normal JIT, JIT/OSR, and a 32 MiB heap with
  pre/post heap verification match independent Python results. The program
  allocates over one million objects plus arrays/strings, checks Unicode,
  recursion and exceptions, and completes four explicit full collections while
  preserving a live object. See `evidence/native-runtime-validation.json`.
- LLDB observes installation of a normal JIT entry, checks the Method's stored
  pointer, and single-steps an instruction at that executable address.
  `evidence/jit-entry-proof.txt` records the address and advanced PC.
- LLDB observes OSR preparation, the reconstructed native PC, and execution of
  an instruction there. The 10-million-iteration OSR program agrees with Python
  at `9000054.399517853`, including GC and a live object. See
  `evidence/osr-entry-proof.txt` and `evidence/osr-runtime-validation.json`.
- Native probes pass Mach-O external call/tail-branch/addend linking and execution,
  1,000 fiber switches, RW-to-RX code publication, and native integer typedef
  mapping. Unsupported immediate types remain rejected. See
  `evidence/native-port-probes.txt`.
- Disassembly of the entire runtime dylib contains zero scalar x18/w18 register
  uses. See `evidence/runtime-x18-audit.txt`.
- A final incremental build passes, source whitespace checks pass, and all 180
  timed batch samples are finite and positive with all 36 workload checksums
  correct. No Crux files were changed by this experiment.

## Build identity and review

- Host: Apple M1 Max, macOS-26.6.2-arm64-arm-64bit; 32 GiB RAM.
- Dart: Dart SDK version: 3.13.3 (stable) (Tue Sep 1 01:07:17 2026 -0700) on "macos_arm64".
- Runtime commit: `6b3a0de5e971b667a1e46e17283595df67a99f0b`.
- Frontend commit: `3271e689443900dbce3ad766c881f397a38e2c76`.
- Build: Apple Clang, Release/O3/product configuration, VIXL backend; LLVM backend
  off, 64-bit managed pointers. See `native/macos-arm64.cmake`.
- Complete source patches: `native/macos-port.patch`, `native/vixl-macos.patch`,
  `native/frontend-appleclang.patch`. Runtime file list:
  `native/changed-runtime-files.txt`.
- `native/PORTING.md` explains Mach-O generation/relocations, reserved x18,
  native integer types, platform sources, shared process state, ICU and build
  compatibility. No optimizer or GC algorithm was replaced.
- `evidence/results.json` retains all commands, references, samples, RSS values,
  and SHA-256 identities of the executable, runtime dylibs, frontend, bytecode,
  Dart kernel and AOT executable, patch, and toolchain.

## Limits and discarded runs

This is a local experimental port of **ArkTS-Sta**, not an upstream-supported
macOS distribution or a result for every shipping ArkTS runtime. The complete
upstream unit/integration suite has not been run. Native Ark AOT and JIT debug
ELF-image emission have not been ported/validated. The JIT/OSR debugger proofs
use focused test settings; benchmark commands use normal JIT/OSR defaults.
The machine was not isolated from other applications; three process repeats
are a useful local measurement, not a broad language ranking.

An initial timing run divided integral ArkTS timestamps before conversion,
truncating sub-millisecond values. It is explicitly marked invalid in
`evidence/invalid-integer-division-results.json` and excluded. The fixed harness
converts elapsed time with `Long.toDouble` and rejects zero/nonfinite samples.
The historical build blocker in `evidence/static-runtime-build-failure.txt`
is superseded by the completed native port.

## Reproduce

```sh
python3 build_source.py --runtime-only
python3 verify_runtime.py
python3 native/verify_port.py
python3 native/run_jit_proof.py
python3 native/run_jit_proof.py --osr  # after compiling bench/osr_smoke.ets
python3 run_bench.py --runs 3
```

The README contains initial setup and the OSR compilation command. No commits,
pushes, system package installations, or changes to Crux are part of this work.
