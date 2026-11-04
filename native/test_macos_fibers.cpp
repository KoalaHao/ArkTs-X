#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>
#include "runtime/fibers/arch/aarch64/context_layout.h"

using Context = uint8_t[FCTX_LEN_BYTES];
extern "C" int GetCurrentContext(Context*);
extern "C" int SwitchContext(Context*, const Context*);
extern "C" int UpdateContext(Context*, void (*)(void*), void*, uint8_t*, size_t);

struct State {
  alignas(16) Context main{};
  alignas(16) Context child{};
  int turns = 0;
};

static void childMain(void* raw) {
  auto* state = static_cast<State*>(raw);
  uint64_t local = 0x1122334455667788ULL;
  for (;;) {
    assert(local == 0x1122334455667788ULL);
    ++state->turns;
    assert(SwitchContext(&state->child, &state->main) == 0);
  }
}

int main() {
  State state;
  std::vector<uint8_t> stack(256 * 1024);
  assert(GetCurrentContext(&state.child) == 0);
  assert(UpdateContext(&state.child, childMain, &state, stack.data(), stack.size()) == 0);
  // This slot must remain irrelevant on Darwin, including when it contains an
  // invalid pointer. Its offset and the remainder of the context stay unchanged.
  const uint64_t poison = 0xbad0bad0bad0bad0ULL;
  std::memcpy(state.child + FCTX_GPR_OFFSET_BYTES_R18, &poison, sizeof(poison));
  for (int i = 1; i <= 1000; ++i) {
    assert(SwitchContext(&state.main, &state.child) == 0);
    assert(state.turns == i);
  }
  std::puts("Native Darwin fiber save/restore passed 1000 switches");
}
