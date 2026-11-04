#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <sys/mman.h>
#include <unistd.h>

int main() {
  const size_t size = static_cast<size_t>(sysconf(_SC_PAGESIZE));
  void* page = mmap(nullptr, size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANON, -1, 0);
  assert(page != MAP_FAILED);
  const uint32_t code[] = {0x52800540, 0xd65f03c0};  // mov w0,#42; ret
  std::memcpy(page, code, sizeof(code));
  __builtin___clear_cache(static_cast<char*>(page), static_cast<char*>(page) + sizeof(code));
  assert(mprotect(page, size, PROT_READ | PROT_EXEC) == 0);
  assert(reinterpret_cast<int (*)()>(page)() == 42);
  assert(munmap(page, size) == 0);
  std::puts("Native RW-to-RX executable memory passed");
}
