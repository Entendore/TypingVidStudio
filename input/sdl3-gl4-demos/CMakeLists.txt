# =============================================================================
#  CMakeLists.txt - SDL3 + OpenGL 4.x + GLAD2 + GLM demo suite
# =============================================================================
cmake_minimum_required(VERSION 3.16)
project(sdl3_gl4_demos LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_C_STANDARD 11)

# compile_commands.json -> clangd / IDE tooling picks this up automatically.
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)

# ---------------------------------------------------------------------------
# GLAD2 loader (generated into third_party/glad by the scaffolding script).
# NOTE: the system OpenGL library is deliberately NOT linked - GLAD resolves
#       every function at runtime via SDL_GL_GetProcAddress.
# ---------------------------------------------------------------------------
add_library(glad STATIC third_party/glad/src/gl.c)
target_include_directories(glad PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/third_party/glad/include)

# ---------------------------------------------------------------------------
# SDL3 via its CMake config package:
#   Linux: libsdl3-dev / SDL3-devel / sdl3 | macOS: brew install sdl3
#   Windows: vcpkg install sdl3   (or -DCMAKE_PREFIX_PATH=<SDL3 install>)
# ---------------------------------------------------------------------------
find_package(SDL3 REQUIRED CONFIG)
find_package(glm CONFIG QUIET)

# ---------------------------------------------------------------------------
# Shared header-only helpers (common/*.hpp) as an INTERFACE target.
# ---------------------------------------------------------------------------
add_library(demo_common INTERFACE)
target_include_directories(demo_common INTERFACE
    ${CMAKE_CURRENT_SOURCE_DIR})
# stb is a SYSTEM include dir: warnings coming from stb_image.h itself are
# suppressed so warnings in OUR code stay readable.
target_include_directories(demo_common SYSTEM INTERFACE
    ${CMAKE_CURRENT_SOURCE_DIR}/third_party/stb)
target_link_libraries(demo_common INTERFACE glad SDL3::SDL3)
# Warnings apply to the demos (which link demo_common) but NOT to glad.c.
target_compile_options(demo_common INTERFACE
    $<$<CXX_COMPILER_ID:MSVC>:/W4>
    $<$<NOT:$<CXX_COMPILER_ID:MSVC>>:-Wall -Wextra -Wpedantic>)
if(glm_FOUND)
    target_link_libraries(demo_common INTERFACE glm::glm)
else()
    message(STATUS "glm CMake package not found - assuming GLM is on the default include path")
endif()

# ---------------------------------------------------------------------------
# One executable per example source (01_triangle.cpp -> demo_triangle, ...).
# ---------------------------------------------------------------------------
file(GLOB DEMO_SOURCES CONFIGURE_DEPENDS
     ${CMAKE_CURRENT_SOURCE_DIR}/[0-9][0-9]_*.cpp)

# Demo 11 needs stb_image.h; skip it (with a note) when it wasn't downloaded.
if(NOT EXISTS ${CMAKE_CURRENT_SOURCE_DIR}/third_party/stb/stb_image.h)
    list(FILTER DEMO_SOURCES EXCLUDE REGEX "11_stb_image")
    message(STATUS "third_party/stb/stb_image.h not found - "
                   "skipping demo_stb_image (see README troubleshooting)")
endif()

foreach(src ${DEMO_SOURCES})
    get_filename_component(name ${src} NAME_WE)              # e.g. 09_shadows
    string(REGEX REPLACE "^[0-9]+_" "demo_" exe ${name})     # -> demo_shadows
    add_executable(${exe} ${src})
    target_link_libraries(${exe} PRIVATE demo_common)
endforeach()

# Demo 11 loads "assets/logo.png" relative to the CWD - copy the asset tree
# next to the binary so the demo runs from any working directory.
if(TARGET demo_stb_image)
    add_custom_command(TARGET demo_stb_image POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy_directory
                ${CMAKE_CURRENT_SOURCE_DIR}/assets
                $<TARGET_FILE_DIR:demo_stb_image>/assets
        COMMENT "Copying assets next to demo_stb_image")
endif()
