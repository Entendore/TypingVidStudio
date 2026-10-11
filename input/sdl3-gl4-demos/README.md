# SDL3 + OpenGL 4.x + GLAD2 + GLM demo suite

Eleven standalone, heavily commented C++17 demos that build on each other:
from a spinning triangle to shadow mapping, geometry-shader ribbons and
compute shaders.

## Requirements

| Tool | Notes |
|---|---|
| CMake >= 3.16 | presets additionally need >= 3.20 |
| C++17 compiler | GCC, Clang or MSVC |
| SDL3 (>= 3.2) | dev package: `libsdl3-dev` / `SDL3-devel` / `brew install sdl3` / `vcpkg install sdl3` |
| GLM | header-only: `libglm-dev` / `brew install glm` / `vcpkg install glm` |
| GLAD2 loader | already generated into `third_party/glad` by the scaffold script |

## Build

    ./build.sh                 # everything (Release)
    ./build.sh run demo_shadows
    ./build.sh list

The manual / IDE-friendly way (needs CMake >= 3.20 for presets):

    cmake --preset default && cmake --build --preset default

or classic:

    cmake -B build -DCMAKE_BUILD_TYPE=Release
    cmake --build build -j

## The demos

| Binary | Concepts | Controls |
|---|---|---|
| demo_triangle | shaders, VAO/VBO, uniforms, MVP | - |
| demo_textured_quad | UVs, texture units, mipmaps, EBO | - |
| demo_cube | depth test, culling, matrix order | - |
| demo_camera | relative mouse, dt movement, FOV zoom | WASD/mouse/E/Q/Shift/wheel |
| demo_lighting | Blinn-Phong, normal matrix, attenuation | - |
| demo_instancing | 3000 objects in one draw call | - |
| demo_compute | GL 4.3 compute + attribute-less rendering | - |
| demo_postprocess | FBO + fullscreen effect pass | 0-3 switch effects |
| demo_shadows | shadow mapping + PCF | M shows the depth map |
| demo_geometry_shader | GS ribbons from GL_LINES | wheel = thickness |
| demo_stb_image | stb_image.h PNG loading | F toggles filtering |

Every window shows live FPS in the title bar. All demos run with a **debug
GL context**: spec violations are reported to stderr via
`glDebugMessageCallback` (see `common/gl_app.hpp`). Wrap suspicious calls in
`GL_CHECK(...)` to get file/line for `glGetError` results.

## Troubleshooting

- **SDL3 not found** - pass its install prefix:
  `cmake -B build -DCMAKE_PREFIX_PATH=/path/to/sdl3-install`
- **macOS** - Apple caps OpenGL at 4.1; `demo_compute`, `demo_shadows`
  (depth-FBO layout used here) and parts of the others assume 4.3.
- **demo_stb_image missing** - `third_party/stb/stb_image.h` wasn't
  downloaded. Re-run the scaffold script (needs internet) or place the file
  there manually; CMake skips that one demo in the meantime.
- **Regenerate GLAD** - `python3 -m pip install glad2`, then
  `python3 -m glad --api=gl=4.6 --profile=core --out-path=third_party/glad`
- **Debug vs Release** - Debug builds enable `GL_CHECK` (per-call
  `glGetError`) and the synchronous debug callback; noticeably slower.

## Project layout

    common/gl_app.hpp     SDL3 + GL context + debug callback + clock helpers
    common/shader.hpp     shader compile/link + uniform setters
    common/geometry.hpp   cube mesh + VAO/VBO/EBO helper
    common/texture.hpp    procedural textures
    01..11_*.cpp          one standalone demo per file
    assets/               logo.png (used by demo 11, copied to build dir)
    third_party/glad      GLAD2 loader (gl 4.6 core)
    third_party/stb       stb_image.h (single-header image loader)
