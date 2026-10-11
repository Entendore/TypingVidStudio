// =============================================================================
//  11_stb_image.cpp - loading real image files with stb_image.h
// =============================================================================
//  Concepts: the STB_IMAGE_IMPLEMENTATION macro (define it in EXACTLY ONE
//            .cpp of the whole program), stbi_load() + the file's channel
//            count, Y-flip on load (image files are top-down, GL textures
//            are bottom-up), choosing GL formats from the channel count,
//            switching filters at runtime, graceful fallback on failure.
//
//  Files used (created by the scaffolding script):
//      assets/logo.png               - the texture (generated PNG)
//      third_party/stb/stb_image.h   - downloaded single-header loader
//
//  The CMake build COPIES assets/ next to every binary (POST_BUILD step),
//  so the executable can be run from any working directory.
//  Controls: F = toggle linear/nearest filtering. Esc quits.
// =============================================================================
#define STB_IMAGE_IMPLEMENTATION    // ^ must appear in exactly ONE .cpp!
#include "stb/stb_image.h"

#include "common/gl_app.hpp"
#include "common/shader.hpp"
#include "common/geometry.hpp"
#include "common/texture.hpp"
#include <cmath>
#include <cstdio>

static const char* VS = R"GLSL(#version 430 core
layout(location = 0) in vec3 aPos;
layout(location = 2) in vec2 aUV;       // location 2 = UV in our Mesh layout
uniform mat4 uModel;
uniform mat4 uVP;
out vec2 vUV;
void main() {
    vUV = aUV;
    gl_Position = uVP * (uModel * vec4(aPos, 1.0));
}
)GLSL";

static const char* FS = R"GLSL(#version 430 core
in vec2 vUV;
out vec4 FragColor;
uniform sampler2D uTex;
void main() { FragColor = texture(uTex, vUV); }
)GLSL";

int main() {
    GLApp app;
    if (!app.init("11 - stb_image")) return 1;

    Shader shader;
    shader.build(VS, FS);
    const Mesh cube = makeCubeMesh();

    glEnable(GL_DEPTH_TEST);
    glEnable(GL_CULL_FACE);

    // ---- load the image -------------------------------------------------------
    // PNG stores row 0 at the TOP; GL texture coordinate (0,0) addresses the
    // BOTTOM-left. This one-liner flips every load so textures aren't upside
    // down (the alternative is flipping the UVs in the mesh).
    stbi_set_flip_vertically_on_load(true);

    int imgW = 0, imgH = 0, channels = 0;
    // Last arg 0 = "keep the file's original channel count". You can also
    // force e.g. 4 to always get RGBA regardless of the file.
    unsigned char* pixels = stbi_load("assets/logo.png",
                                      &imgW, &imgH, &channels, 0);

    GLuint tex = 0;
    if (pixels) {
        std::printf("Loaded assets/logo.png: %dx%d, %d channels\n",
                    imgW, imgH, channels);

        // Match the GL format to what the file actually contains.
        GLenum format   = (channels == 4) ? GL_RGBA :
                          (channels == 3) ? GL_RGB  : GL_RED;
        GLenum internal = (channels == 4) ? GL_RGBA8 :
                          (channels == 3) ? GL_RGB8  : GL_R8;

        glGenTextures(1, &tex);
        glBindTexture(GL_TEXTURE_2D, tex);
        // RGB rows aren't 4-byte aligned by default -> relax unpack alignment
        // or every third row of an RGB image comes out garbled.
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
        glTexImage2D(GL_TEXTURE_2D, 0, internal, imgW, imgH, 0,
                     format, GL_UNSIGNED_BYTE, pixels);
        stbi_image_free(pixels);      // GL copied the pixels - free the file data
        glGenerateMipmap(GL_TEXTURE_2D);  // mip chain tames minification shimmer
    } else {
        // Asset missing? stbi_failure_reason() says why. Keep running with a
        // procedural checker so the demo still shows *something*.
        std::fprintf(stderr, "stbi_load failed: %s - using checker fallback\n",
                     stbi_failure_reason());
        tex = makeCheckerTexture(256, 8);
    }

    bool linear = true;
    auto applyFilters = [&] {
        glBindTexture(GL_TEXTURE_2D, tex);
        // MIN filter may include mipmaps (mip chain exists in both cases);
        // MAG filtering never uses mipmaps - always GL_LINEAR or GL_NEAREST.
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER,
            linear ? GL_LINEAR_MIPMAP_LINEAR : GL_NEAREST_MIPMAP_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER,
            linear ? GL_LINEAR : GL_NEAREST);

        char title[128];
        if (imgW)
            std::snprintf(title, sizeof title,
                          "11 - stb_image %dx%dx%d [F: %s]",
                          imgW, imgH, channels, linear ? "linear" : "nearest");
        else
            std::snprintf(title, sizeof title,
                          "11 - stb_image (fallback checker) [F: %s]",
                          linear ? "linear" : "nearest");
        app.setBaseTitle(title);      // GLApp appends " | NN FPS"
    };
    applyFilters();

    bool running = true;
    while (running) {
        SDL_Event e;
        while (SDL_PollEvent(&e)) {
            if (e.type == SDL_EVENT_QUIT) running = false;
            if (e.type == SDL_EVENT_KEY_DOWN) {
                if (e.key.key == SDLK_ESCAPE) running = false;
                if (e.key.key == SDLK_F) {          // toggle filtering
                    linear = !linear;
                    applyFilters();
                }
            }
        }

        app.beginFrame();
        const float t = app.time();
        const float aspect = app.height > 0
                           ? float(app.width) / float(app.height) : 1.0f;
        const glm::mat4 vp = glm::perspective(glm::radians(50.0f), aspect,
                                              0.1f, 100.0f)
                           * glm::translate(glm::mat4(1.0f),
                                            glm::vec3(0, 0, -3.2f));
        const glm::mat4 model =
            glm::rotate(glm::mat4(1.0f), t * 0.9f, glm::vec3(0.5f, 1.0f, 0.2f)) *
            glm::scale (glm::mat4(1.0f), glm::vec3(1.4f));

        glClearColor(0.10f, 0.12f, 0.16f, 1.0f);
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);

        shader.use();
        shader.setMat4("uVP", vp);
        shader.setMat4("uModel", model);
        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, tex);
        shader.setInt("uTex", 0);
        cube.draw();

        app.endFrame();
    }

    glDeleteTextures(1, &tex);
    cube.destroy();
    return 0;
}
