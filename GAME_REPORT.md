# Game-framework CPU workloads: Dart and static ArkTS

**All 54 isolated runs pass the independent checkpoints. Dart JIT is competitive
with ArkTS here and faster on particles; allocation tail latency differs sharply.
A separate combined run reproducibly faults during GC in the experimental ArkTS
build. The isolated timings do not establish whole-engine stability.**

Host: Apple M1 Max, macOS 26.6.2 ARM64, Dart 3.13.3. ArkTS-Sta uses the same
source-built runtime/patches as the earlier microbenchmarks; no runtime code was
changed for this experiment. Exact revisions and artifact hashes are in the raw data.

## Results

Milliseconds per simulated CPU tick; lower is better. Each cell is p50 / p99.
Metrics are the median of three fresh-process metrics, with 3000 measured ticks
per workload per process. p99 uses nearest rank within each process.

| Workload: p50 / p99 ms | Dart kernel JIT | Dart AOT | ArkTS JIT |
|---|---:|---:|---:|
| 10k polymorphic behaviours | 0.0315 / 0.0505 | 0.0902 / 0.1214 | 0.0322 / 0.0467 |
| 50k 3D particles | 0.1980 / 0.2624 | 0.2679 / 0.3465 | 0.3110 / 0.3809 |
| 8191 transforms + culling | 0.1667 / 0.2737 | 0.2081 / 0.3492 | 0.1616 / 0.2756 |
| 2048 circle colliders | 0.2432 / 0.3440 | 0.2357 / 0.3193 | 0.2571 / 0.3477 |
| 2000 new events/tick | 0.0214 / 0.0362 | 0.0388 / 0.0620 | 0.0274 / 0.4050 |
| 2000 pooled events/tick | 0.0121 / 0.0225 | 0.0234 / 0.0369 | 0.0137 / 0.0211 |

These numbers cover CPU work, including pauses during the timed calls. They are
not FPS and exclude rendering, GPU submission, native renderer/FFI integration,
audio, input, asset streaming, and a real game's complete frame. Worlds evolve
across ticks, use a fixed 1/60 simulation step, and run unpaced without VSync.

The behaviours case is close between the JITs; Dart AOT is slower on this
polymorphic pattern. ArkTS narrowly leads the transform case. Dart JIT leads the
particle case, and Dart AOT leads collision detection. Runtime mode and workload
shape matter more than a single overall language ranking.

For transient events, ArkTS's median tick is small but its p99 is roughly 11 times
Dart JIT's in this configuration. Pooling brings both p99 values near 0.02 ms.
That is an observed allocation/lifetime effect; without correlating every pause
with GC events, individual spikes cannot all be attributed to the collector.

## What each tick does

| Case | Persistent simulation work |
|---|---|
| behaviours_10k | 10000 object instances, three behaviour classes, virtual updates, movement/steering/drag and wrapping |
| particles_50k | 50000 3D particles, seven Float64 SoA streams, gravity/wind, lifetimes and deterministic respawning |
| scene_8191 | Binary hierarchy of 8191 3x4 affine transforms; 1/16 local transforms change per tick, parent changes invalidate descendants; six-plane box culling |
| collisions_2048 | Move 2048 circles, rebuild a 32x32 linked uniform grid, query nine neighbouring cells, compute unique circle contacts |
| events_alloc_2k | Allocate 2000 event records/tick, apply them to 4096 health values, retain eight generations and read older events |
| events_pool_2k | Same events/results/lifetimes using eight preallocated rotating buffers, 16000 pooled records in total |

This is a synthetic matched-pattern suite, informed by current Pyxis transform,
particle-buffer and spatial-grid code. It does not import or benchmark Pyxis.
Scene matrices use packed buffers, while the behaviours case exercises object
fields and polymorphic calls. Collision detection is 2D circles, not a full 3D
physics solver. Both float buffers use 64-bit elements. ArkTS uses 32-bit `int`
for bounded indices/fields; Dart uses its normal native `int`.

## Measurement and correctness

- One workload per fresh process; runtime/case order is reproducibly shuffled
  each repeat. Both JIT modes start from frontend-compiled input (`.dill`/`.abc`).
- Construct fixtures and run independent checkpoints, warm that workload for at
  least one second, create a fresh world, then measure 3000 sequential ticks.
- Dart uses Stopwatch ticks/frequency; ArkTS uses Chrono.nanoNow and converts the
  elapsed integer to floating point before calculating milliseconds. Clock/warmup
  durations are checked against Python's process wall clock.
- Fixture construction, preallocation, checkpoint replay and JSON output are
  outside per-tick timing. Peak RSS includes the entire process, including them.
  Pool creation is therefore excluded from steady-state timing but is not free.
- Checkpoints at ticks 8 and 128 run before and after timing, checking cold and
  warmed code against independent Python results. The entire 3000-tick measured
  trajectory is consumed in a checksum, not replayed tick-for-tick in Python.
- The Python oracle uses flat actor records, per-particle records, unconditional
  transform recomputation rather than caching, and sweep-and-prune rather than
  a grid. Collision reference results are additionally checked by all-pairs
  search at ticks 1 and 128. Allocation and pooling share one event oracle.
- All 162000 frame samples are finite and positive. All 216 checkpoint values
  pass. This is three local repeats, not a confidence bound for every game.

## Memory

These are per-workload process peaks, not idle VM footprints. Default heap/GC
policies differ. ArkTS uses the existing 64-bit managed-pointer configuration
required by this port.

| Workload: median peak RSS, MiB | Dart kernel JIT | Dart AOT | ArkTS JIT |
|---|---:|---:|---:|
| 10k polymorphic behaviours | 60.44 | 16.31 | 21.27 |
| 50k 3D particles | 66.77 | 25.02 | 27.12 |
| 8191 transforms + culling | 62.42 | 20.61 | 25.58 |
| 2048 circle colliders | 56.61 | 14.52 | 18.91 |
| 2000 new events/tick | 88.59 | 49.30 | 29.17 |
| 2000 pooled events/tick | 59.16 | 16.84 | 21.83 |

Dart AOT has the lowest measured peak in five of these six workloads. ArkTS has
the lowest peak in the allocation-heavy case. The previous microbenchmark's
memory ordering therefore does not generalize to every game workload.

## Follow-up: memory and GC diagnostics

The allocation workload exposes a memory/latency trade-off in these default
configurations. Its peak RSS is 88.59 / 49.30 / 29.17 MiB for Dart JIT / Dart AOT /
ArkTS. Pooling reduces those peaks to 59.16 / 16.84 / 21.83 MiB.

Primary, uninstrumented event-allocation measurements across 9000 ticks:

| Metric | Dart JIT | Dart AOT | ArkTS JIT |
|---|---:|---:|---:|
| p99 tick, ms (median of process p99s) | 0.0362 | 0.0620 | 0.4050 |
| Worst tick, ms | 0.6275 | 0.4983 | 0.6133 |
| Ticks above 0.25 ms | 27 | 20 | 297 |
| Pooled-event p99 tick, ms | 0.0225 | 0.0369 | 0.0211 |

A low p99 does not mean no occasional longer pause: Dart JIT's worst tick was
similar to ArkTS's, but slow ticks were less frequent. These are whole tick
durations, not individually identified GC pauses, and include OS/runtime effects.

`python3 probe_game_gc.py` performs separate instrumented runs using copies of
these kernels, one additional end marker, and verbose collector logging. It does
not modify the primary sources/binaries or contribute performance samples. Dart
AOT tracing uses dartaotruntime plus an AOT snapshot so VM logging flags can be
passed explicitly. One diagnostic run per mode/case recorded:

| 3000 event-allocation ticks | Dart JIT | Dart AOT | ArkTS JIT |
|---|---:|---:|---:|
| Logged collections completed in measured stage | 9 scavenges | 8 scavenges | 83 G1 cycles |
| Logged median duration / pause interval, ms | 0.3 | 0.2 | 0.290 |
| Logged largest duration / pause interval, ms | 0.7 | 0.4 | 0.497 |

Ark's 83 cycles contained 104 explicit pause intervals (some cycles have more
than one). Its accumulated logged pauses were about 29.7 ms; Dart's logged young
collection times summed to 3.5 / 1.9 ms. The Dart column is the verbose-GC `time`
field for Scavenge; the Ark column is its explicit `paused` intervals, not total
concurrent cycle time. These logging runs have overhead and are not a precise
one-to-one correlation with the uninstrumented frame samples.

The traces support more frequent collection as a contributor to ArkTS's heavier
allocation tail here, rather than showing that each individual Dart collection
is always shorter. Dart's logs reach about 32 MiB of new-generation use before
these scavenges; Ark commonly reports freeing 3–5 MiB per cycle. Heap policies
and object layout differ, so this is not a language-intrinsic memory ranking.

With pooling, **none of the three diagnostic runs logged a collection between
the measured-stage markers**. That applies to these 3000 ticks, not to all game
lifetimes. Neither these pauses nor headless tick times establish actual visible
stutter or end-to-end frame rate. The unresolved combined-run GC fault below
remains a separate, material stability limitation of this experimental build.

Raw logs, commands and checksums: `evidence/game/gc/receipts.json`, `*.log` and
`*.measured.log`; extracted GC statistics: `evidence/game/gc/summary.json`;
primary frame-tail counts: `evidence/game/gc/frame-tail-summary.json`.

## Tail outliers

Worst single tick across all 9000 samples per mode/case; these include OS
scheduling/background activity as well as runtime effects.

| Workload: worst observed tick, ms | Dart kernel JIT | Dart AOT | ArkTS JIT |
|---|---:|---:|---:|
| 10k polymorphic behaviours | 0.1904 | 0.2113 | 0.1487 |
| 50k 3D particles | 0.4414 | 3.9459 | 0.4801 |
| 8191 transforms + culling | 0.4298 | 0.5252 | 5.0377 |
| 2048 circle colliders | 1.7869 | 0.4282 | 0.4558 |
| 2000 new events/tick | 0.6275 | 0.4983 | 0.6133 |
| 2000 pooled events/tick | 0.0659 | 0.1145 | 0.0532 |

## Combined-run failure — unresolved

The no-argument program runs all six workloads sequentially in one process.
With the same current bytecode used by the isolated measurements, the ArkTS
build reproducibly raises EXC_BAD_ACCESS while G1 scans roots at the transition
into `events_alloc_2k` checks. LLDB stops in
`G1GC<EtsLanguageConfig>::InGCSweepRange`; an invalid object reference reaches
that function. Root cause is not established. An earlier diagnostic with OSR
disabled also failed at that transition, so disabling OSR did not resolve it.

The original non-debug run timed out in the signal/GC fault path; that timeout
is not a timing result. The combined diagnostic and incomplete run are excluded
from the performance tables. No GC check was disabled and no collector was
changed to produce isolated numbers. Case isolation also provides separate RSS
measurements and avoids unrelated receiver-type profiles sharing a call site.
It does **not** fix or excuse this observed stability failure.

See `evidence/game/combined-diagnostic.json` for the exact command and matching
bytecode SHA-256, `evidence/game/combined-ark-gc-fault.txt` for the current trace,
and `build/game-ark-diagnostic-sample.txt` for the original sample. This is a
finding about this experimental macOS build, not proof that an upstream or
shipping HarmonyOS runtime has the same defect. Full application/native renderer
integration remains unvalidated, and native Ark AOT remains unported.

## Files and reproduction

- `bench/game.ets`: shared algorithm source.
- `generate_game_dart.py`, `bench/game.dart`: restricted declaration/API adapters
  and the readable generated Dart implementation. This is not a general transpiler.
- `game_references.py`: independent untimed oracles.
- `run_game_bench.py`: builds/analyzes both sources, runs fresh processes,
  validates checkpoints/samples, retains raw data, reports percentiles/RSS.
- `evidence/game/results.json`: all 54 commands, 162000 samples, checksums, RSS,
  machine/revision data and source/binary/patch SHA-256 identities.
- `evidence/game/table.md`: compact results. `build/game-build.log`: build evidence.

```sh
python3 run_game_bench.py --runs 3
```

A single isolated case can also be invoked directly:

```sh
dart build/game.dill events_alloc_2k
build/game_dart_aot events_alloc_2k
build/ark-source/bin/ark --load-runtimes=ets \
  --boot-panda-files=build/ark-source/plugins/ets/etsstdlib.abc \
  --compiler-enable-jit=true build/game.abc game.ETSGLOBAL::main -- events_alloc_2k
```

Use the recorded LLDB command for the combined failure; an unguarded direct
combined run can remain in its fault handler. The runner uses bounded process
groups and preserves partial logs on timeout. No runtime, Crux, or Pyxis code
was changed for this suite, and no commits or pushes were made.
