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
route is the upstream Linux x86_64 build under WSL2. It needed **no runtime source
changes**, only build plumbing: a toolchain file, pinned asmjit/zydis, and
portable runners.

## Correctness

| Check | Result |
|---|---|
| C++ interpreter, IRtoC interpreter, JIT, JIT+OSR, GC stress (32 MiB heap, pre/post heap verification) | all pass (`native-runtime-validation.json`) |
| Microbenchmark processes (5 runs × 3 modes) | 15/15, all checksums correct |
| Game workloads, one case per process (3 runs × 6 cases × 3 modes) | 54/54, all checkpoints correct |
| All six game workloads sequentially in **one** Ark process | 3/3 pass. The macOS ARM64 port crashes here in G1 root scanning, which suggests that fault is specific to the Mac port |
| JIT actually engaged | interpreter-only is 30–50× slower (sieve 19.5 ms, vectors 62 ms vs 0.39 / 1.37 ms with JIT) |

## Microbenchmarks

Median of 5 fresh-process medians, ms per operation, lower is better.
The method is unchanged from [BENCHMARKS.md](BENCHMARKS.md): 1 s warmup, 5 calibrated batches.

| Workload | Dart JIT (kernel) | Dart AOT | **ArkTS JIT/OSR** | Ark vs best Dart |
|---|---:|---:|---:|---:|
| sieve | 0.5039 | **0.3828** | 0.3945 | 1.03× slower |
| vectors (float64) | 0.5195 | **0.4414** | 1.3672 | 3.10× slower |
| objects | **0.1045** | 0.1123 | 0.1465 | 1.40× slower |
| text (split/UTF-16) | 0.7227 | 0.8203 | **0.6523** | 1.11× faster |

Run-to-run spread was ≤ 4% for every cell. As a reference, native Windows Dart
(no WSL) measured JIT 0.49 / 0.43 / 0.094 / 0.73 and AOT 0.39 / 0.36 / 0.10 / 0.77 ms.
That is within a few percent of WSL2 Dart, except vectors, where native Windows is about 18% faster.
So WSL2 is not distorting the comparison materially.

### Peak RSS (whole process, all four workloads)

| Dart JIT | Dart AOT | ArkTS JIT |
|---:|---:|---:|
| 76.2 MiB | 40.8 MiB | **37.4 MiB** |

## Game-framework CPU workloads

p50 / p99 tick time in ms (3000 ticks, fresh process per case, median of 3 runs).

| Workload | Dart JIT | Dart AOT | **ArkTS JIT** |
|---|---:|---:|---:|
| behaviours_10k (polymorphic) | **0.032** / 0.055 | 0.050 / 0.069 | 0.041 / 0.077 |
| particles_50k (3D float math) | **0.129** / 0.184 | 0.167 / 0.233 | 0.361 / 0.475 |
| scene_8191 (transforms/culling) | **0.117** / 0.201 | 0.153 / 0.257 | 0.204 / 0.343 |
| collisions_2048 (spatial grid) | 0.219 / 0.371 | **0.213** / 0.283 | 0.289 / 0.396 |
| events_alloc_2k (transient alloc) | **0.018** / 0.042 | 0.026 / 0.071 | 0.024 / **0.570** |
| events_pool_2k (pooled) | **0.010** / 0.017 | 0.016 / 0.026 | 0.015 / 0.022 |

Peak RSS per case: Dart JIT 50–83 MiB, Dart AOT 7–41 MiB, ArkTS 26–35 MiB.

## Takeaways

- **No overall winner, but Dart leads on most CPU work here.** ArkTS wins only on
  text processing (about 11%) and roughly ties on the byte sieve.
- **Float64-heavy code is ArkTS's weak spot**: about 3× slower on vectors and 2.2–2.8× on
  particles. This matches the macOS result (2.3× there), so it reflects the Ark
  JIT's code quality, not the platform.
- **Dart's JIT beats its AOT** on most game workloads (the JIT has runtime type
  feedback for polymorphic/float code). ArkTS JIT trails the best Dart mode by
  1.3–2.8× at p50. It still beats Dart AOT on behaviours, events_alloc and events_pool.
- **Allocation tail latency**: ArkTS events_alloc p99 (0.57 ms) is 8–14× Dart's.
  That points to GC pauses. Pooling removes the gap (0.022 ms).
- **Memory**: ArkTS uses less than Dart JIT everywhere. Dart AOT is smallest on
  the game cases (6.7–17.7 MiB except the allocation case).
- Compared with the Apple M1 Max results in [REPORT.md](REPORT.md), ArkTS keeps its
  text lead but loses its sieve lead on x86_64 (tie here, 1.35× faster on the Mac).

## Limits

CPU-only, single-threaded microbenchmarks and simulated game ticks. They say nothing
about UI, rendering, startup or I/O. ArkTS loop integers are 32-bit; Dart `int` is
64-bit. Ark on Linux uses 32-bit managed pointers (the Mac port uses 64-bit), so
memory figures are not directly comparable across the two reports. Native Ark AOT
was not built. The full upstream test suite was not run.
