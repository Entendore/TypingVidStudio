// =============================================================================
//  06_instancing.cpp - hardware instancing (core since GL 3.3)
// =============================================================================
//  Concepts: glDrawArraysInstanced, per-instance vertex attributes via
//            glVertexAttribDivisor, GPU-side animation driven by uniforms.
//            Instancing is THE tool for crowds, particles, vegetation...
// =============================================================================
#include "common/gl_app.hpp"
#include "common/shader.hpp"
#include <cmath>
#include <vector>

static const char* VS = R"GLSL(#version 430 core
layout(location = 0) in vec2 aPos;     // per-vertex quad corner
layout(location = 2) in vec2 aOffset;  // per-INSTANCE position (divisor = 1)
uniform mat4  uVP;
uniform float uTime;
out vec3 vColor;
void main() {
    float d = length(aOffset);
    // Each instance is a flat quad; bend the field into a radial wave.
    vec3 p = vec3(aPos + aOffset, 0.0);
    p.z = 0.5f * sin(uTime * 2.0 - d * 1.2) * exp(-d * 0.22);
    // Hue from distance from center + time -> a slowly cycling rainbow.
    vColor = 0.5 + 0.5 * cos(vec3(0.0, 2.1, 4.2) + d * 0.9 - uTime * 0.8);
    gl_Position = uVP * vec4(p, 1.0);
}
)GLSL";

static const char* FS = R"GLSL(#version 430 core
in vec3 vColor;
out vec4 FragColor;
void main() { FragColor = vec4(vColor, 1.0); }
)GLSL";

int main() {
    GLApp app;
    if (!app.init("06 - Instancing")) return 1;

    Shader shader;
    shader.build(VS, FS);

    // One small quad = 6 vertices (2 triangles, no index buffer needed).
    const float quad[] = {
        -0.05f,-0.05f,   0.05f,-0.05f,   0.05f, 0.05f,
        -0.05f,-0.05f,   0.05f, 0.05f,  -0.05f, 0.05f,
    };

    // Per-instance data: positions on a golden-angle spiral (sunflower).
    constexpr int N = 3000;
    std::vector<glm::vec2> offsets(N);
    for (int i = 0; i < N; ++i) {
        const float f = float(i) / N;
        const float r = 6.5f * std::sqrt(f);
        const float a = i * glm::radians(137.508f);   // golden angle
        offsets[i] = { r * std::cos(a), r * std::sin(a) };
    }

    GLuint vao = 0, vbo = 0, ibo = 0;
    glGenVertexArrays(1, &vao);
    glBindVertexArray(vao);

    glGenBuffers(1, &vbo);
    glBindBuffer(GL_ARRAY_BUFFER, vbo);
    glBufferData(GL_ARRAY_BUFFER, sizeof quad, quad, GL_STATIC_DRAW);
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 2 * sizeof(float),
                          (const void*)0);
    glEnableVertexAttribArray(0);

    glGenBuffers(1, &ibo);
    glBindBuffer(GL_ARRAY_BUFFER, ibo);
    glBufferData(GL_ARRAY_BUFFER, N * sizeof(glm::vec2), offsets.data(),
                 GL_STATIC_DRAW);
    glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, 2 * sizeof(float),
                          (const void*)0);
    glEnableVertexAttribArray(2);
    // THE key call: advance this attribute once per INSTANCE, not per vertex.
    glVertexAttribDivisor(2, 1);

    glBindVertexArray(0);

    bool running = true;
    while (running) {
        SDL_Event e;
        while (SDL_PollEvent(&e)) {
            if (e.type == SDL_EVENT_QUIT) running = false;
            if (e.type == SDL_EVENT_KEY_DOWN &&
                e.key.key == SDLK_ESCAPE) running = false;
        }

        app.beginFrame();
        const float t = app.time();
        const float aspect = app.height > 0
                           ? float(app.width) / float(app.height) : 1.0f;

        // Camera slowly circles the field.
        const glm::vec3 eye(8.0f * std::sin(t * 0.25f), 4.5f,
                            8.0f * std::cos(t * 0.25f));
        const glm::mat4 vp = glm::perspective(glm::radians(55.0f), aspect,
                                              0.1f, 100.0f)
                           * glm::lookAt(eye, glm::vec3(0),
                                         glm::vec3(0, 1, 0));

        glClearColor(0.08f, 0.09f, 0.12f, 1.0f);
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);

        shader.use();
        shader.setMat4("uVP", vp);
        shader.setFloat("uTime", t);

        glBindVertexArray(vao);
        // ONE draw call for all 3000 quads (18000 vertices total).
        glDrawArraysInstanced(GL_TRIANGLES, 0, 6, N);
        app.endFrame();
    }

    glDeleteBuffers(1, &ibo);
    glDeleteBuffers(1, &vbo);
    glDeleteVertexArrays(1, &vao);
    return 0;
}
