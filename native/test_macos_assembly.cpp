#include <cassert>
#include <fstream>
#include <sstream>
#include "irtoc/backend/macos_assembly.h"

using ark::irtoc::MacAssemblyRelocation;
using ark::irtoc::WriteMacArm64Function;

static std::vector<uint8_t> instructions(std::initializer_list<uint32_t> words) {
  std::vector<uint8_t> bytes;
  for (auto word : words) {
    for (unsigned shift = 0; shift != 32; shift += 8) bytes.push_back(word >> shift);
  }
  return bytes;
}

int main(int argc, char** argv) {
  assert(argc == 2);
  std::ofstream out(argv[1]);
  std::string error;
  const auto call = instructions({0xa9bf7bfd, 0x910003fd, 0x94000000,
                                   0xa8c17bfd, 0xd65f03c0});
  assert(WriteMacArm64Function(out, "port_call", call, {{8, 2, 0, "callee"}}, 16, &error));
  const auto branch = instructions({0x14000000});
  assert(WriteMacArm64Function(out, "port_tail", branch, {{0, 2, 0, "callee"}}, 16, &error));
  assert(WriteMacArm64Function(out, "port_offset", branch, {{0, 2, 4, "offset_target"}}, 16, &error));
  out.close();
  assert(out.good());
  auto reject = [&](const std::vector<uint8_t>& code,
                    const std::vector<MacAssemblyRelocation>& relocs) {
    std::ostringstream ignored;
    error.clear();
    assert(!WriteMacArm64Function(ignored, "bad", code, relocs, 16, &error));
    assert(!error.empty());
  };
  reject(branch, {{0, 283, 0, "callee"}});  // ELF tag must not pass as Mach-O.
  reject(branch, {{4, 2, 0, "callee"}});    // Out of bounds.
  reject(branch, {{1, 2, 0, "callee"}});    // Misaligned.
  reject(branch, {{0, 2, 1, "callee"}});    // Invalid branch addend.
  reject(branch, {{0, 2, 0, "callee"}, {0, 2, 0, "callee"}});
  reject(branch, {{0, 2, 0, "bad\nlabel"}});
  reject(instructions({0xd503201f}), {{0, 2, 0, "callee"}});  // Not a branch.
  reject(instructions({0x14000001}), {{0, 2, 0, "callee"}});  // Nonzero immediate.
  reject({0}, {});  // Partial instruction.
}
