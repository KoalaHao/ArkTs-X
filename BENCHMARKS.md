# Original benchmark methodology

For reproducible setup, source fetching, and supported build commands, see
[README.md](README.md). This document describes the original experiment.
Do not follow its historical setup notes in place of the current README.

## Game-framework workloads

`python3 run_game_bench.py --runs 3` builds and runs six persistent CPU workloads:
polymorphic behaviours, 3D particles, cached hierarchical transforms/culling,
spatial-grid collisions, transient events, and pooled events. Each case runs in
a fresh process with 3000 timed ticks. The report includes p50/p99, peak RSS,
independent checkpoints, and a separately recorded combined-run GC fault in the
experimental ArkTS build. See [GAME_REPORT.md](GAME_REPORT.md) and
`evidence/game/results.json`. These CPU timings are not GPU timings or FPS.

These benchmarks run independently of Crux.

The primary experiment builds OpenHarmony's **static** ArkTS compiler and
runtime (`ets2panda` and `runtime_core/static_core`) from source. The benchmark runner uses only the source-built runtime.

## Workloads

| Name | One operation |
|---|---|
| sieve | Allocate a byte buffer and count primes below 200001 |
| vectors | Initialize two 32768-element float64 buffers, perform 12 update passes, sum the results |
| objects | Allocate 10000 class instances, mutate each over four passes, read all results |
| text | Split 4096 mixed ASCII/Chinese log lines and extract/tag their contents |

These are single-threaded microbenchmarks. They do not measure UI, rendering,
LLM latency, networking, full application startup, or a complete engine/agent.
The byte and float buffers have matching element widths. ArkTS loop/index fields
use `int` (32-bit), while native Dart uses its normal `int`; values stay within
32-bit range. This is an idiomatic implementation comparison rather than a
claim of identical machine-level operations.

Each workload has an independent Python reference checksum. The harness warms
each workload for at least one second, calibrates a batch size, and records five
batch samples. It prints checksums and a consumed result so the benchmark work
is observable. The Python runner runs fresh processes serially in a reproducibly
shuffled order, validates all checksums, and retains every sample. Its summary
uses the median of process medians. Millisecond timing is amortized over batches.
Peak RSS includes the entire process and all four workloads.
Both JIT modes start from precompiled input: a Dart kernel (`.dill`) and Ark
bytecode (`.abc`). Their source frontends run before the timed processes. The
discarded earlier source-launch memory comparison is retained separately in
`evidence/source-launch-results.json` and is not the primary comparison.

## Build and source provenance

Use the current [README.md](README.md) for the complete clean-checkout build.
`bootstrap_deps.py` now fetches the exact commits in `source-revisions.json`
and applies all recorded patches automatically. New output goes to `results/`;
the original benchmark records are preserved under `evidence/`.

The toolchain selects the existing 64-bit managed-pointer configuration because
Darwin does not reserve the low heap required by 32-bit managed pointers.
See [native/PORTING.md](native/PORTING.md) for the platform changes.

## Status

The experimental native ARM64 runtime builds and runs on this Mac. Both
interpreters and JIT-enabled normal/OSR modes pass the same independent
arithmetic/allocation/Unicode/recursion/exception checks. Forced full GC and
a 32 MiB heap run preserve live objects. Native ABI tests pass, and disassembly
of the full runtime library contains no scalar x18/w18 instructions.

LLDB separately proves installation/execution of a normal JIT entry and an OSR
transition into reconstructed loop state. These checks run outside timing:

```sh
python3 native/run_jit_proof.py
build/ark-source/bin/es2panda_stdlib_compiler --extension=ets --opt-level=2 \
  --output=build/osr_smoke.abc bench/osr_smoke.ets
python3 native/run_jit_proof.py --osr
```

Evidence: `evidence/native-runtime-validation.json`,
`evidence/jit-entry-proof.txt`, `evidence/osr-entry-proof.txt`,
`evidence/osr-runtime-validation.json`, `evidence/native-port-probes.txt`, and
`evidence/runtime-x18-audit.txt`. The historical initial failure remains in
`evidence/static-runtime-build-failure.txt`.

This is a local experimental port, not a supported upstream macOS distribution.
The full upstream test suite has not been run. Ark native AOT remains unported;
The recovery kit defaults to runtime + bootstrap frontend and excludes AOT. `REPORT.md` records
completed benchmark results and limitations.
