# Native Linux x86_64 host build (also used under WSL2 on Windows).
# Linux x86_64 is an existing upstream platform: no codegen/ABI patches are
# needed here. This only pins the compiler and mirrors the kit's build options.
set(CMAKE_C_COMPILER clang)
set(CMAKE_CXX_COMPILER clang++)
set(CMAKE_CROSSCOMPILING FALSE)
set(ARK_BENCH_DEPS_PREPARED ON CACHE BOOL "Dependencies fetched by bootstrap_deps.py")
set(CMAKE_POLICY_VERSION_MINIMUM 3.5 CACHE STRING "Allow upstream dependencies")
set(PANDA_ENABLE_CCACHE OFF CACHE BOOL "")
set(PANDA_LLVM_BACKEND OFF CACHE BOOL "")
set(PANDA_CROSS_COMPILER OFF CACHE BOOL "")
set(PANDA_PRODUCT_BUILD ON CACHE BOOL "Use upstream release configuration" FORCE)
set(PANDA_WITH_ETS ON CACHE BOOL "")
# The cross-values auxiliary configure would otherwise use upstream's
# host_gcc_default toolchain and re-run install-third-party (network fetches).
set(PANDA_CROSS_X86_64_TOOLCHAIN_FILE "${CMAKE_CURRENT_LIST_FILE}" CACHE FILEPATH "")
# Newer clang (19+) adds warnings that upstream (pinned to clang 14) treats as errors.
set(CMAKE_CXX_FLAGS "-Wno-unused-command-line-argument -Wno-error=deprecated-literal-operator -Wno-error=unnecessary-virtual-specifier -Wno-error=deprecated-declarations -Wno-error=unused-parameter -Wno-unknown-warning-option" CACHE STRING "" FORCE)
set(CMAKE_C_FLAGS "-Wno-unused-command-line-argument" CACHE STRING "" FORCE)
