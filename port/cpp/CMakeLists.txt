# Build the Unscripted core as a library an engine can link.
#
# Header-only above the ABI, so there is exactly one translation unit: the C ABI
# itself. Everything else is includes. That is what makes the console builds
# cheap -- no build system to port, no dependencies to vendor, no link order to
# get wrong.
#
#   cmake -S port/cpp -B build && cmake --build build
#
# Produces `libusc` (shared by default; -DBUILD_SHARED_LIBS=OFF for static, which
# is what a console wants) and, with -DUSC_BUILD_PROBE=ON, the C99 program that
# proves the header is callable from C.
cmake_minimum_required(VERSION 3.16)
project(usc LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_C_STANDARD 99)

option(USC_BUILD_PROBE "Build the C99 ABI probe" OFF)

add_library(usc abi/usc.cpp)
target_include_directories(usc
    PUBLIC  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/abi>
    PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/include)
set_target_properties(usc PROPERTIES
    POSITION_INDEPENDENT_CODE ON
    # Only the ABI is exported. Nothing above it is part of the contract, and a
    # plugin that reached past it would be binding to something the probes do
    # not compare.
    CXX_VISIBILITY_PRESET hidden
    VISIBILITY_INLINES_HIDDEN ON)
if(BUILD_SHARED_LIBS)
    target_compile_definitions(usc PRIVATE USC_BUILD_SHARED)
    target_compile_definitions(usc INTERFACE USC_USE_SHARED)
endif()

# NOT `-ffast-math`. Measured: it moves one value by 1 ULP, and in a runtime
# where a seeded draw decides who overhears what, one bit is potentially a
# different world. See port/README.md.
if(MSVC)
    target_compile_options(usc PRIVATE /fp:precise)
else()
    target_compile_options(usc PRIVATE -fno-fast-math)
endif()

if(USC_BUILD_PROBE)
    add_executable(usc_abi_probe abi/abi_probe.c)
    target_link_libraries(usc_abi_probe PRIVATE usc)
endif()

install(TARGETS usc ARCHIVE DESTINATION lib LIBRARY DESTINATION lib
                    RUNTIME DESTINATION bin)
install(FILES abi/usc.h DESTINATION include)
