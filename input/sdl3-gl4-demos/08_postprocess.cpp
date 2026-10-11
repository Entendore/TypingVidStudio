// =============================================================================
//  08_postprocess.cpp - render-to-texture + post processing
// =============================================================================
//  Concepts: framebuffer objects (FBO), color texture + depth renderbuffer
//            attachments, completeness checking, a second fullscreen pass
//            that samples the scene and applies effects.
//  Controls: keys 0-3 switch effect (0 none, 1 invert, 2 CRT, 3 noir), Esc quits.
// =============================================================================
#include "common/gl_app.hpp"
#include "common/shader.hpp"
#include "common/geometry.hpp"
#include <cmath>
#include <cstdio>

// --- scene shader: flat-colored cubes ----------------------------------------
static const char* SCENE_VS = R"GLSL(#version 430 core
layout(location = 0) in vec3 aPos;
uniform mat4 uModel;
uniform mat4 uVP;
void main() { gl_Position = uVP * (uModel * vec4(aPos, 1.0)); }
)GLSL";

static const char* SCENE_FS = R"GLSL(#version 430 core
uniform vec3 uColor;
out vec4 FragColor;
void main() { FragColor = vec4(uColor, 1.0); }
)GLSL";

// --- post pass: fullscreen triangle sampling the scene texture ----------------
static const char* POST_VS = R"GLSL(#version 430 core
out vec2 vUV;
void main() {
    vec2 p = vec2(gl_VertexID == 1 ? 3.0 : -1.0,
                  gl_VertexID == 2 ? 3.0 : -1.0);
    gl_Position = vec4(p, 0.0, 1.0);
    vUV = p * 0.5 + 0.5;
}
)GLSL";

static const char* POST_FS = R"GLSL(#version 430 core
in vec2 vUV;
out vec4 FragColor;
uniform sampler2D uScene;
uniform int uEffect;    // 0 = none, 1 = invert, 2 = CRT, 3 = noir vignette
void main() {
    vec2 d = vUV - 0.5;
    vec3 c;

    if (uEffect == 2) {
        // Chromatic aberration: sample R and B slightly off-center.
        float k = 0.006 * length(d);
        c = vec3(texture(uScene, vUV + d * k).r,
                 texture(uScene, vUV).g,
                 texture(uScene, vUV - d * k).b);
        // Scanlines.
        c *= 0.85 + 0.15 * sin(vUV.y * 900.0);
    } else {
        c = texture(uScene, vUV).rgb;
    }

    if (uEffect == 1) c = 1.0 - c;                       // negative film
    if (uEffect == 3) {                                  // grayscale + vignette
        float g = dot(c, vec3(0.299, 0.587, 0.114));
        c = vec3(g) * smoothstep(0.85, 0.25, length(d));
    }

    FragColor = vec4(c, 1.0);
}
)GLSL";

int main() {
    GLApp app;
    if (!app.init("08 - Post processing (keys 0-3)")) return 1;

    Shader scene, post;
    scene.build(SCENE_VS, SCENE_FS);
    post.build(POST_VS, POST_FS);
    const Mesh cube = makeCubeMesh();

    GLuint emptyVao = 0;
    glGenVertexArrays(1, &emptyVao);   // attribute-less fullscreen triangle

    // ---- offscreen target state ------------------------------------------------
    GLuint fbo = 0, sceneTex = 0, depthRbo = 0;
    GLsizei fw = 0, fh = 0;

    // (Re)create FBO attachments whenever the window size changes. Doing the
    // check once per frame is simpler than tracking resize events.
    auto resizeTargets = [&](int w, int h) {
        if (w == fw && h == fh && fbo != 0) return;
        fw = w; fh = h;
        if (sceneTex) { glDeleteTextures(1, &sceneTex);      sceneTex = 0; }
        if (depthRbo) { glDeleteRenderbuffers(1, &depthRbo); depthRbo = 0; }
        if (!fbo) glGenFramebuffers(1, &fbo);

        sceneTex = makeEmptyTexture(w, h, GL_RGBA8);   // color attachment

        // Renderbuffers are write-only GPU images - perfect for depth.
        glGenRenderbuffers(1, &depthRbo);
        glBindRenderbuffer(GL_RENDERBUFFER, depthRbo);
        glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, w, h);

        glBindFramebuffer(GL_FRAMEBUFFER, fbo);
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0,
                               GL_TEXTURE_2D, sceneTex, 0);
        glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT,
                                  GL_RENDERBUFFER, depthRbo);
        // Always verify - an incomplete FBO silently draws nothing.
        if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE)
            std::fprintf(stderr, "FBO incomplete!\n");
        glBindFramebuffer(GL_FRAMEBUFFER, 0);
    };

    const char* effectNames[] = { "off", "invert", "CRT", "noir" };
    int effect = 2;

    bool running = true;
    while (running) {
        SDL_Event e;
        while (SDL_PollEvent(&e)) {
            if (e.type == SDL_EVENT_QUIT) running = false;
            if (e.type == SDL_EVENT_KEY_DOWN) {
                if (e.key.key == SDLK_ESCAPE) running = false;
                if (e.key.key >= SDLK_0 && e.key.key <= SDLK_3) {
                    effect = e.key.key - SDLK_0;
                    char title[64];
                    std::snprintf(title, sizeof title,
                                  "08 - Post processing (effect: %s)",
                                  effectNames[effect]);
                    // setBaseTitle: GLApp keeps appending " | NN FPS".
                    app.setBaseTitle(title);
                }
            }
        }

        app.beginFrame();
        resizeTargets(app.width, app.height);
        const float t = app.time();

        const float aspect = fh > 0 ? float(fw) / float(fh) : 1.0f;
        const glm::mat4 vp = glm::perspective(glm::radians(50.0f), aspect,
                                              0.1f, 100.0f)
                           * glm::translate(glm::mat4(1.0f),
                                            glm::vec3(0, 0, -4));

        // ---- PASS 1: render the scene INTO THE FBO --------------------------
        glBindFramebuffer(GL_FRAMEBUFFER, fbo);
        glViewport(0, 0, fw, fh);                 // render at target's size!
        glEnable(GL_DEPTH_TEST);
        glClearColor(0.13f, 0.15f, 0.19f, 1.0f);
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);

        scene.use();
        scene.setMat4("uVP", vp);
        struct { glm::mat4 m; glm::vec3 c; } cubes[] = {
            { glm::rotate(glm::mat4(1.0f), t * 0.9f,
                          glm::vec3(0.5f, 1.0f, 0.3f)),
              glm::vec3(0.2f, 0.8f, 1.0f) },
            { glm::rotate(glm::mat4(1.0f), -t * 1.3f, glm::vec3(0, 1, 0)) *
              glm::translate(glm::mat4(1.0f), glm::vec3(1.8f, 0, 0)) *
              glm::scale(glm::mat4(1.0f), glm::vec3(0.35f)),
              glm::vec3(1.0f, 0.6f, 0.2f) },
            { glm::rotate(glm::mat4(1.0f), t * 1.7f, glm::vec3(0, 1, 0)) *
              glm::translate(glm::mat4(1.0f), glm::vec3(-1.8f, 0.2f, 0)) *
              glm::scale(glm::mat4(1.0f), glm::vec3(0.35f)),
              glm::vec3(1.0f, 0.3f, 0.5f) },
        };
        for (const auto& cb : cubes) {
            scene.setMat4("uModel", cb.m);
            scene.setVec3("uColor", cb.c);
            cube.draw();
        }
        glDisable(GL_DEPTH_TEST);

        // ---- PASS 2: draw the FBO's texture to the screen, with effects ------
        // Unbind first: sampling a texture attached to the *bound* FBO is a
        // feedback loop error.
        glBindFramebuffer(GL_FRAMEBUFFER, 0);
        glViewport(0, 0, app.width, app.height);
        glClearColor(0, 0, 0, 1);
        glClear(GL_COLOR_BUFFER_BIT);

        post.use();
        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, sceneTex);
        post.setInt("uScene", 0);
        post.setInt("uEffect", effect);
        glBindVertexArray(emptyVao);
        glDrawArrays(GL_TRIANGLES, 0, 3);

        app.endFrame();
    }

    if (sceneTex) glDeleteTextures(1, &sceneTex);
    if (depthRbo) glDeleteRenderbuffers(1, &depthRbo);
    if (fbo)      glDeleteFramebuffers(1, &fbo);
    glDeleteVertexArrays(1, &emptyVao);
    cube.destroy();
    return 0;
}
