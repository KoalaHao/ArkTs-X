# ArkTS static runtime vs Dart on Windows (WSL2)

**Host:** Intel Core i5-13600KF (20 threads), 48 GiB RAM, Windows 11 Pro 26200,
WSL2 Debian 13 (x86_64), clang 19.1.7. **Dart:** 3.13.4 linux_x64 inside WSL2;
3.13.2 windows_x64 for the native reference row. **Ark:** the same pinned
`runtime_core`/`ets_frontend` commits as the macOS experiment, built as the
upstream Linux x86_64 target (32-bit managed pointers, x86_64 JIT backend).

Raw receipts are in [evidence/windows-wsl2/](evidence/windows-wsl2/).
Every process passed its checksum against the independent Python references.

## Why WSL2 and not native Win32

The static runtime's execution engine depends on POSIX signals, `mmap`, futexes,
fibers and Unix JIT code publication. Upstream's Windows support covers host
*tools* via MinGW cross-compilation, not the runtime/JIT. On Windows the practical
route is the upstream Linux x86_64 build under WSL2. The interpreter and JIT needed **no runtime source
changes**, only build plumbing: a toolchain file, pinned asmjit/zydis, and
portable runners. AOT needed one 6-line fix (`native/aot-gnu-stack.patch`). The
`.an` ELF writer omitted `PT_GNU_STACK`, so glibc 2.41 refused to load the images.

## Correctness

| Check | Result |
|---|---|
| C++ interpreter, IRtoC interpreter, JIT, JIT+OSR, GC stress (32 MiB heap, pre/post heap verification) | all pass (`native-runtime-validation.json`) |
| Microbenchmark processes (5 runs × 4 modes) | 20/20, all checksums correct |
| Game workloads, one case per process (3 runs × 6 cases × 4 modes) | 72/72, all checkpoints correct |
| All six game workloads sequentially in **one** Ark process | JIT 3/3 and AOT 3/3 pass. The macOS ARM64 port crashes here in G1 root scanning, which suggests that fault is specific to the Mac port |
| JIT actually engaged | interpreter-only is 30–50× slower (sieve 19.5 ms, vectors 62 ms vs 0.39 / 1.37 ms with JIT) |
| Native AOT (`ark_aot` → `.an`, JIT disabled) | `aot` and `aot-gc-stress` validation modes pass; all AOT benchmark checksums correct |

## Microbenchmarks

Median of 5 fresh-process medians, ms per operation, lower is better.
The method is unchanged from [BENCHMARKS.md](BENCHMARKS.md): 1 s warmup, 5 calibrated batches.
ArkTS AOT runs with the stdlib and the program both compiled by `ark_aot`, and the JIT off.

| Workload | Dart JIT (kernel) | Dart AOT | ArkTS JIT/OSR | ArkTS AOT | Best Ark vs best Dart |
|---|---:|---:|---:|---:|---:|
| sieve | 0.5039 | **0.3848** | 0.3945 | 0.3965 | 1.03× slower |
| vectors (float64) | 0.5273 | **0.4531** | 1.3672 | 1.5078 | 3.0× slower |
| objects | **0.1055** | 0.1152 | 0.1514 | 0.1699 | 1.4× slower |
| text (split/UTF-16) | 0.7539 | 0.8281 | 0.6602 | **0.4062** | 1.86× faster |

Run-to-run spread was 7% or less in every cell, and 3% or less in most. As a reference, native Windows Dart
(no WSL) measured JIT 0.49 / 0.43 / 0.094 / 0.73 and AOT 0.39 / 0.36 / 0.10 / 0.77 ms.
That is within a few percent of WSL2 Dart, except vectors, where native Windows is about 18% faster.
So WSL2 is not distorting the comparison materially.

### Peak RSS (whole process, all four workloads)

| Dart JIT | Dart AOT | ArkTS JIT | ArkTS AOT |
|---:|---:|---:|---:|
| 76.1 MiB | 40.8 MiB | **37.1 MiB** | 38.0 MiB |

## Game-framework CPU workloads

p50 / p99 tick time in ms (3000 ticks, fresh process per case, median of 3 runs).

| Workload | Dart JIT | Dart AOT | ArkTS JIT | ArkTS AOT |
|---|---:|---:|---:|---:|
| behaviours_10k (polymorphic) | **0.029** / 0.065 | 0.050 / 0.080 | 0.040 / 0.072 | 0.109 / 0.159 |
| particles_50k (3D float math) | **0.129** / 0.200 | 0.167 / 0.261 | 0.357 / 0.483 | 0.392 / 0.503 |
| scene_8191 (transforms/culling) | **0.117** / 0.212 | 0.154 / 0.267 | 0.204 / 0.360 | 0.241 / 0.408 |
| collisions_2048 (spatial grid) | 0.220 / 0.385 | **0.214** / 0.314 | 0.289 / 0.415 | 0.273 / 0.389 |
| events_alloc_2k (transient alloc) | **0.018** / 0.046 | 0.026 / 0.055 | 0.025 / 0.569 | 0.043 / 0.596 |
| events_pool_2k (pooled) | **0.010** / 0.016 | 0.016 / 0.028 | 0.015 / 0.026 | 0.031 / 0.048 |

Peak RSS per case: Dart JIT 49–83 MiB, Dart AOT 6–42 MiB, ArkTS JIT 26–35 MiB, ArkTS AOT 25–35 MiB.

## Takeaways

- **No overall winner, but Dart leads on most CPU work here.** ArkTS wins clearly on
  text processing (1.86× with AOT, 1.14× with JIT) and roughly ties on the byte sieve.
- **Float64-heavy code is ArkTS's weak spot**: about 3× slower on vectors and 2.1–2.8× on
  particles, in both JIT and AOT. This matches the macOS result (2.3× there), so it reflects
  Ark's optimizing compiler, not the platform.
- **ArkTS AOT ≈ JIT on monomorphic loops, worse on dynamic dispatch.** AOT matches the
  JIT on sieve and collisions, and is 10–20% slower on vectors, objects and particles. It is
  2.7× slower on polymorphic behaviours and 1.7–2× on events, because it has no runtime
  profile for devirtualization or inlining. The big AOT win is text: the AOT-compiled
  stdlib (string split, builders) runs much faster than the JIT's stdlib path.
- **AOT gives no startup win at hello-world scale**: both modes start in about 11 ms. The
  stdlib `.an` is a one-off 6 s compile producing 15 MiB.
- **Dart's JIT beats its AOT** on most game workloads (runtime type feedback). ArkTS JIT
  trails the best Dart mode by 1.3–2.8× at p50, but beats Dart AOT on behaviours,
  events_alloc and events_pool.
- **Allocation tail latency**: ArkTS events_alloc p99 (about 0.57–0.60 ms, JIT or AOT) is about
  10–13× Dart's. That points to GC pauses. Pooling removes the gap.
- **Memory**: ArkTS (either mode) uses less than Dart JIT everywhere. Dart AOT is
  smallest on the game cases except the allocation case.
- Compared with the Apple M1 Max results in [REPORT.md](REPORT.md), ArkTS keeps its
  text lead but loses its sieve lead on x86_64 (tie here, 1.35× faster on the Mac).

## Limits

CPU-only, single-threaded microbenchmarks and simulated game ticks. They say nothing
about UI, rendering or I/O. ArkTS loop integers are 32-bit; Dart `int` is 64-bit.
Ark on Linux uses 32-bit managed pointers (the Mac port uses 64-bit), so memory
figures are not directly comparable across the two reports. Ark AOT is validated on
Linux x86_64 only; the Mac port still has no AOT. The full upstream test suite was not run.
