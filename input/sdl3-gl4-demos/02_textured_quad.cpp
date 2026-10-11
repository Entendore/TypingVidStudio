// =============================================================================
//  02_textured_quad.cpp - textures & index buffers
// =============================================================================
//  Concepts: UV coordinates, sampler uniforms, texture units, wrap/filter
//            modes, mipmaps, EBO (element/index buffer) drawing.
// =============================================================================
#include "common/gl_app.hpp"
#include "common/shader.hpp"
#include "common/texture.hpp"
#include <cmath>

static const char* VS = R"GLSL(#version 430 core
layout(location = 0) in vec2 aPos;
layout(location = 1) in vec2 aUV;
uniform mat4  uMVP;
uniform float uScroll;              // animated UV offset
out vec2 vUV;
void main() {
    vUV = aUV + vec2(uScroll, 0.0); // slide the texture horizontally
    gl_Position = uMVP * vec4(aPos, 0.0, 1.0);
}
)GLSL";

static const char* FS = R"GLSL(#version 430 core
in vec2 vUV;
out vec4 FragColor;
uniform sampler2D uTex;             // samples the texture bound to a unit
uniform vec3 uTint;
void main() {
    FragColor = texture(uTex, vUV) * vec4(uTint, 1.0);
}
)GLSL";

int main() {
    GLApp app;
    if (!app.init("02 - Textured quad")) return 1;

    Shader shader;
    shader.build(VS, FS);

    // A quad needs only 4 corners; an index buffer tells GL which 3-vertex
    // triangles to form, so corner data is never duplicated.
    const float verts[] = {
        //  x,y          u,v   (UVs go to 3 -> texture tiles via GL_REPEAT)
        -0.5f,-0.5f,   0.0f,0.0f,   // bottom-left
         0.5f,-0.5f,   3.0f,0.0f,   // bottom-right
         0.5f, 0.5f,   3.0f,3.0f,   // top-right
        -0.5f, 0.5f,   0.0f,3.0f,   // top-left
    };
    const GLuint idx[] = { 0,1,2, 2,3,0 };      // two CCW triangles

    GLuint vao = 0, vbo = 0, ebo = 0;
    glGenVertexArrays(1, &vao);
    glBindVertexArray(vao);
    glGenBuffers(1, &vbo);
    glBindBuffer(GL_ARRAY_BUFFER, vbo);
    glBufferData(GL_ARRAY_BUFFER, sizeof verts, verts, GL_STATIC_DRAW);
    glGenBuffers(1, &ebo);
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, ebo); // recorded by the VAO
    glBufferData(GL_ELEMENT_ARRAY_BUFFER, sizeof idx, idx, GL_STATIC_DRAW);
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(float),
                          (const void*)0);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(1, 2, GL_FLOAT, GL_FALSE, 4 * sizeof(float),
                          (const void*)(2 * sizeof(float)));
    glEnableVertexAttribArray(1);
    glBindVertexArray(0);

    const GLuint checker = makeCheckerTexture(256, 8);

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
        const glm::mat4 mvp = glm::perspective(glm::radians(45.0f), aspect,
                                               0.1f, 100.0f)
                            * glm::translate(glm::mat4(1.0f), glm::vec3(0,0,-3))
                            * glm::rotate(glm::mat4(1.0f),
                                          0.3f * std::sin(t * 0.7f),
                                          glm::vec3(0, 0, 1));

        glClearColor(0.10f, 0.12f, 0.16f, 1.0f);
        glClear(GL_COLOR_BUFFER_BIT);

        shader.use();
        // Texture unit 0 -> our texture; point the sampler uniform at unit 0.
        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, checker);
        shader.setInt("uTex", 0);
        shader.setFloat("uScroll", 0.15f * t);
        shader.setVec3("uTint", glm::vec3(0.6f + 0.4f * std::sin(t), 1, 1));
        shader.setMat4("uMVP", mvp);

        glBindVertexArray(vao);
        glDrawElements(GL_TRIANGLES, 6, GL_UNSIGNED_INT, nullptr); // indexed!
        app.endFrame();
    }

    glDeleteBuffers(1, &ebo);
    glDeleteBuffers(1, &vbo);
    glDeleteVertexArrays(1, &vao);
    glDeleteTextures(1, &checker);
    return 0;
}
