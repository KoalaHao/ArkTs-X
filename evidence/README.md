# Historical experiment evidence

These are the original receipts from the macOS ARM64 experiment, preserved
before packaging this recovery repository. Original commands contain the
experiment's absolute local paths; they are historical records, not setup
instructions. Artifact hashes refer to those original binaries/scripts.

- `results.json`: corrected primary microbenchmarks.
- `game/results.json`: 54 isolated game-workload processes and raw tick samples.
- `game/gc/`: instrumented GC runs, pauses and frame-tail extraction.
- `game/combined-diagnostic.json`, `game/combined-ark-gc-fault.txt`: unresolved
  combined-workload crash; do not omit this when interpreting the passing runs.
- `native-runtime-validation.json`: five focused execution-mode checks.
- `jit-entry-proof.txt`, `osr-entry-proof.txt`: debugger execution evidence.
- `native-port-probes.txt`, `runtime-x18-audit.txt`: ABI and register checks.

`invalid-integer-division-results.json` is an invalid, excluded early run;
`source-launch-results.json` is a separate early launch-mode comparison.
Neither is the primary result. Early abort/build-failure logs are retained for
provenance and do not describe the final build status.

New runs write to the ignored `results/` directory and do not overwrite this
historical archive. Build and recovery validation for this packaged checkout is
recorded separately in the repository's `VALIDATION.md`.
