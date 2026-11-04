#include <cassert>
#include <cstdio>
extern "C" int callee(int value) { return value * 7; }
extern "C" int port_call(int value);
extern "C" int port_tail(int value);
extern "C" int port_offset();
asm(".text\n.p2align 2\n.globl _offset_target\n_offset_target:\n"
    "mov w0, #13\nmov w0, #42\nret\n");
int main() {
  assert(port_call(6) == 42);
  assert(port_tail(6) == 42);
  assert(port_offset() == 42);
  std::puts("Mach-O BL, B, and branch-addend execution passed");
}
