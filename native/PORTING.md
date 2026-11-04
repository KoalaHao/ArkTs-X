# Native macOS ARM64 static ArkTS port

This experiment targets `runtime_core/static_core` (ArkTS-Sta), at the revisions
in `source-revisions.json`. It is not a port of ArkUI or a claim about every
shipping ArkTS runtime. No Crux sources are modified.

## Native code and object format

Upstream omits several code-generation targets on macOS. The experimental
`ARK_BENCH_ENABLE_MAC_CODEGEN` CMake switch includes those existing sources.
ARM64 B/BL relocation emission uses Darwin's `ARM64_RELOC_BRANCH26` tag on Mac.

The IRtoC generator previously wrote ELF objects unconditionally. On Mac it now
writes assembly, preserving instruction words and translating external branch
sites into symbolic B/BL instructions. Apple's assembler produces the Mach-O
objects. The emitter rejects unsupported relocation types, invalid instruction
sites, duplicate sites, invalid symbols, and misaligned/out-of-range sites.
Upstream generator validation remains enabled. Generated output is not edited.

The native fixture links and executes an external call, tail branch, and branch
with a four-byte symbol addend, each returning 42. `otool -rv` exposes BR26 and
ADDEND/BR26 relocation pairs.

## Darwin's reserved x18

Darwin reserves the scalar x18 register. This target excludes it from the default
register-allocation set. Generic save/restore operations retain the pre-existing
x18 frame slot but use xzr for it: stores write zero and loads discard that slot.
The register masks, slot numbering, stack adjustment, frame metadata, and all
other register offsets remain unchanged. Floating-point d18 is unaffected.

Fiber assembly saves/restores x19 separately on Darwin, leaving the x18 context
slot unused. The proxy bridge does not restore x18. The native fiber test poisons
that slot and performs 1,000 context switches while checking a live stack local.
The generated IRtoC objects must contain no scalar x18/w18 instructions.
Handwritten runtime/ANI bridges also skip x18 restoration. The OSR bridge uses
x13 as its temporary frame-end pointer on Darwin, then restores it from the
existing OSR register buffer. Buffer/frame layouts are unchanged. The complete
runtime dylib, including generated bridges, has been disassembled and contains
zero scalar x18/w18 instructions.

## Other compatibility changes

- CPU features use Darwin sysctl queries instead of Linux auxiliary vectors.
- The build selects the existing Darwin memory-hook implementation. Requesting
  unsupported allocation restrictions still retains its fatal diagnostic.
- POSIX pipe/exec/wait implementations are included on Mac, and the Linux/GCC
  `-latomic` dependency is excluded.
- Assembly constants remain assembly text instead of passing through Apple
  libtool, which discarded that input.
- ICU initialization is included directly in the runtime object on Mac, beside
  the single statically linked ICU copy. It cannot be dropped as an unreferenced
  archive constructor or initialize a second ICU state in a separate dylib.
- Signal-set calls use parenthesized function names so Darwin's function-like
  macros do not expand after the C++ global namespace qualifier.
- Linux-only heap-dump status constants use the same guard as their consumers.
- Apple Clang warning accommodations are recorded in the toolchain and patches.
- Arkbase is shared for this port, so the launcher and runtime dependencies use
  one process-wide logger/allocator state under Mach-O's two-level binding.
- The existing Apple-only runtime JIT rejection is bypassed only when the
  experimental port flag is enabled; the normal backend-support check remains.
- 64-bit integral immediates are recognized by width when their C++ typedef is
  different from `uint64_t` (Darwin's `uintptr_t`, `intptr_t`, and `size_t`).
  A regression test fails before this fix and passes afterward; bool and long
  double remain invalid, matching the original type contract.
- The existing `PANDA_USE_64_BIT_POINTER` option is enabled. The upstream Mac
  heap allocator does not reserve the low-address range required by its 32-bit
  managed-pointer configuration. Every runtime component and generated constant
  must be rebuilt consistently; memory comparisons must disclose this choice.

## Validation

After building the runtime:

```sh
python3 native/verify_port.py
build/ark-source/bin/es2panda_stdlib_compiler --extension=ets --opt-level=2 \
  --output=build/port_smoke.abc bench/port_smoke.ets
```

The smoke test covers recursion, floating-point loops, one million allocated
objects plus arrays/strings, live references across calls, Unicode operations,
exception handling, and four explicit completed collections with a live anchor.
`python3 verify_runtime.py` runs both interpreters, normal JIT, JIT/OSR, and a
32 MiB heap with pre/post heap verification. Its independent Python reference is:

```
PORT_SMOKE 2543718.392064034 57577374 1 113
```

All five modes independently match those values. Release builds remove compiler
events/debug logging, so `python3 native/run_jit_proof.py` observes entry
installation, stops at the generated instructions, and checks the Method's
installed pointer. It selects only the numeric method and uses synchronous JIT
with hotness zero for focused coverage; those settings are not benchmark flags.
`--osr` observes PrepareOsrEntry, its reconstructed native PC, then execution at
that PC. The 10-million-iteration OSR program also matches the Python result
9000054.399517853 in interpreter and JIT/OSR runs, including GC and a live object.

The standalone executable-memory probe verifies RW -> RX publication on this
Mac. The upstream code allocator already takes alignment from the OS page size;
no code-allocator, GC, object-layout, or stack-map algorithm changes were made.

## Boundaries

Native `ark` execution, normal JIT, OSR, and AOT are separate acceptance steps.
The AOT writer/loader path still needs explicit Mach-O validation and is not
covered by the IRtoC object writer. Do not infer AOT support from a working JIT.
Likewise, focused smoke tests do not establish complete runtime compatibility.

Guidance consulted: runtime_core/static_core root, compiler, irtoc, runtime,
libarkbase, platforms, ETS compiler/runtime AGENTS; IRtoC generated-code,
compiled-runtime-boundary, and JIT workflow knowledge documents. Preserve
generated-source ownership, roots/stack metadata, exception/GC checks, and JIT
selection/install ordering. No production dependencies were added.
