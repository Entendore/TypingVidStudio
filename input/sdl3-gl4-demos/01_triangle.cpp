// =============================================================================
//  01_triangle.cpp - "Hello Triangle" (SDL3 + OpenGL 4.x + GLAD2 + GLM)
// =============================================================================
//  Concepts: shaders, VAO/VBO, vertex attributes, uniforms, event loop, vsync,
//            and GL_CHECK() - an immediate glGetError() wrapper for debugging.
// =============================================================================
#include "common/gl_app.hpp"
#include "common/shader.hpp"

static const char* VS = R"GLSL(#version 430 core
layout(location = 0) in vec3 aPos;   // attribute 0: position
layout(location = 1) in vec3 aCol;   // attribute 1: color
uniform mat4 uMVP;                   // Model * View * Projection
out vec3 vCol;
void main() {
    vCol = aCol;
    gl_Position = uMVP * vec4(aPos, 1.0);
}
)GLSL";

static const char* FS = R"GLSL(#version 430 core
in vec3 vCol;
out vec4 FragColor;                  // the required fragment output in core
void main() { FragColor = vec4(vCol, 1.0); }
)GLSL";

int main() {
    GLApp app;
    if (!app.init("01 - Triangle")) return 1;

    Shader shader;
    shader.build(VS, FS);

    // Interleaved [pos(3) | color(3)] - one triangle.
    const float verts[] = {
        -0.5f,-0.5f,0.0f,   1.0f,0.2f,0.2f,
         0.5f,-0.5f,0.0f,   0.2f,1.0f,0.2f,
         0.0f, 0.6f,0.0f,   0.3f,0.5f,1.0f,
    };

    // The VAO records the attribute setup, so one bind restores everything.
    // GL_CHECK() (from gl_app.hpp) wraps calls with an immediate glGetError()
    // test in debug builds and prints the exact file/line on failure - wrap
    // any call you suspect while debugging.
    GLuint vao = 0, vbo = 0;
    GL_CHECK(glGenVertexArrays(1, &vao));
    GL_CHECK(glBindVertexArray(vao));
    GL_CHECK(glGenBuffers(1, &vbo));
    GL_CHECK(glBindBuffer(GL_ARRAY_BUFFER, vbo));
    GL_CHECK(glBufferData(GL_ARRAY_BUFFER, sizeof verts, verts, GL_STATIC_DRAW));
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 6 * sizeof(float),
                          (const void*)0);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 6 * sizeof(float),
                          (const void*)(3 * sizeof(float)));
    glEnableVertexAttribArray(1);
    glBindVertexArray(0);

    bool running = true;
    while (running) {
        // ---- events --------------------------------------------------------
        SDL_Event e;
        while (SDL_PollEvent(&e)) {
            if (e.type == SDL_EVENT_QUIT) running = false;
            if (e.type == SDL_EVENT_KEY_DOWN &&
                e.key.key == SDLK_ESCAPE) running = false;   // SDL3: e.key.key
        }

        // ---- frame setup: app.beginFrame() refreshes dt, size, viewport ----
        app.beginFrame();
        const float t = app.time();   // seconds since app.init()

        // ---- update (GLM) ---------------------------------------------------
        const float aspect = app.height > 0
                           ? float(app.width) / float(app.height) : 1.0f;
        const glm::mat4 model = glm::rotate(glm::mat4(1.0f),
                                            glm::radians(120.0f) * t,
                                            glm::vec3(0, 0, 1));
        const glm::mat4 view  = glm::translate(glm::mat4(1.0f),
                                               glm::vec3(0, 0, -3));
        const glm::mat4 proj  = glm::perspective(glm::radians(45.0f),
                                                 aspect, 0.1f, 100.0f);

        // ---- draw ------------------------------------------------------------
        glClearColor(0.10f, 0.12f, 0.16f, 1.0f);
        glClear(GL_COLOR_BUFFER_BIT);
        shader.use();
        shader.setMat4("uMVP", proj * view * model);
        glBindVertexArray(vao);
        glDrawArrays(GL_TRIANGLES, 0, 3);

        app.endFrame();   // swap; also updates the " | NN FPS" window title
    }

    glDeleteBuffers(1, &vbo);
    glDeleteVertexArrays(1, &vao);
    return 0;
}
