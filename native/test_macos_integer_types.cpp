#include <cstdint>
#include "compiler/optimizer/code_generator/operands.h"

using ark::compiler::TypeInfo;
using ark::compiler::TypedImm;

static_assert(TypeInfo(uint64_t {42}).IsValid());
static_assert(TypeInfo(int64_t {-42}).IsValid());
static_assert(TypeInfo(uintptr_t {42}).IsValid());
static_assert(TypeInfo(intptr_t {-42}).IsValid());
static_assert(TypeInfo(size_t {42}).IsValid());
static_assert(TypeInfo(uintptr_t {42}) == TypeInfo(uint64_t {42}));
static_assert(TypeInfo(intptr_t {-42}) == TypeInfo(int64_t {-42}));
static_assert(!TypeInfo(true).IsValid());  // Unsupported types stay rejected.
static_assert(!TypeInfo(static_cast<long double>(1)).IsValid());

int main() {
  const TypedImm deopt(uintptr_t {0x123456789ULL});
  return deopt.GetType().ToDataType() == ark::compiler::DataType::INT64 &&
                 deopt.GetImm().GetAsInt() == 0x123456789LL ? 0 : 1;
}
