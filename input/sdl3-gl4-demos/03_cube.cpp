// =============================================================================
//  03_cube.cpp - 3D cube: depth buffer, culling, matrix composition
// =============================================================================
//  Concepts: GL_DEPTH_TEST, GL_CULL_FACE, transform order (rightmost matrix
//            is applied to the vertex first), parented/orbiting transforms.
// =============================================================================
#include "common/gl_app.hpp"
#include "common/shader.hpp"
#include "common/geometry.hpp"

static const char* VS = R"GLSL(#version 430 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;
uniform mat4 uMVP;
out vec3 vCol;
void main() {
    vCol = aNormal * 0.5 + 0.5;   // color = face normal -> each face differs
    gl_Position = uMVP * vec4(aPos, 1.0);
}
)GLSL";

static const char* FS = R"GLSL(#version 430 core
in vec3 vCol;
out vec4 FragColor;
void main() { FragColor = vec4(vCol, 1.0); }
)GLSL";

int main() {
    GLApp app;
    if (!app.init("03 - Cube")) return 1;

    Shader shader;
    shader.build(VS, FS);
    const Mesh cube = makeCubeMesh();

    // 3D essentials: without the depth test, later triangles overwrite
    // nearer ones; culling skips triangles facing away (free ~50%).
    glEnable(GL_DEPTH_TEST);
    glEnable(GL_CULL_FACE);

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
        const glm::mat4 vp = glm::perspective(glm::radians(45.0f), aspect,
                                              0.1f, 100.0f)
                           * glm::translate(glm::mat4(1.0f), glm::vec3(0,0,-4));

        glClearColor(0.10f, 0.12f, 0.16f, 1.0f);
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);  // BOTH buffers

        shader.use();
        shader.setMat4("uVP", vp);

        // Cube 1: spins on two axes. Rotate is applied to the vertex BEFORE
        // the view/projection because it sits rightmost in the product.
        glm::mat4 m1 = glm::rotate(glm::mat4(1.0f), t * 1.1f,
                                   glm::vec3(0.6f, 1.0f, 0.2f));
        shader.setMat4("uModel", m1);
        cube.draw();

        // Cube 2: orbits cube 1. Multiplying "parent * child" composes the
        // transforms - try swapping the two lines to see the difference.
        glm::mat4 m2 = m1
                     * glm::translate(glm::mat4(1.0f), glm::vec3(1.7f, 0, 0))
                     * glm::scale(glm::mat4(1.0f), glm::vec3(0.3f))
                     * glm::rotate(glm::mat4(1.0f), t * 3.0f, glm::vec3(0,1,0));
        shader.setMat4("uModel", m2);
        cube.draw();

        app.endFrame();
    }

    cube.destroy();
    return 0;
}
