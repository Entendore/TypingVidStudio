// =============================================================================
//  04_camera.cpp - player-controlled fly camera
// =============================================================================
//  Concepts: relative mouse mode, app.dt() for frame-rate independent
//            movement, keyboard state, yaw/pitch -> direction vector,
//            FOV zoom, drawing many models.
//  Controls: mouse = look, WASD = move, E/Q or Space/Ctrl = up/down,
//            Shift = fast, mouse wheel = FOV zoom, Esc = quit.
// =============================================================================
#include "common/gl_app.hpp"
#include "common/shader.hpp"
#include "common/geometry.hpp"
#include "common/texture.hpp"
#include <cmath>

static const char* VS = R"GLSL(#version 430 core
layout(location = 0) in vec3 aPos;
layout(location = 2) in vec2 aUV;    // location 2 = UV in our Mesh layout
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
uniform vec3 uColor;
void main() { FragColor = texture(uTex, vUV) * vec4(uColor, 1.0); }
)GLSL";

int main() {
    GLApp app;
    if (!app.init("04 - Fly camera (WASD + mouse)")) return 1;

    Shader shader;
    shader.build(VS, FS);
    const Mesh cube = makeCubeMesh();
    const GLuint checker = makeCheckerTexture(128, 4);

    glEnable(GL_DEPTH_TEST);
    glEnable(GL_CULL_FACE);

    // Capture the mouse: hide cursor and get unlimited relative motion.
    SDL_SetWindowRelativeMouseMode(app.window, true);

    // Camera state.
    glm::vec3 camPos(0.0f, 1.5f, 6.0f);
    float yaw = 0.0f;                       // rotation around Y
    float pitch = 0.0f;                     // rotation around X (clamped)
    float fov = 70.0f;                      // vertical FOV in degrees

    bool running = true;
    while (running) {
        // ---- events --------------------------------------------------------
        SDL_Event e;
        while (SDL_PollEvent(&e)) {
            switch (e.type) {
            case SDL_EVENT_QUIT:
                running = false;
                break;
            case SDL_EVENT_KEY_DOWN:
                if (e.key.key == SDLK_ESCAPE) running = false;
                break;
            case SDL_EVENT_MOUSE_MOTION:
                // xrel/yrel are pixels since the last event (already relative).
                yaw   += e.motion.xrel * 0.0025f;
                pitch -= e.motion.yrel * 0.0025f;   // screen Y grows downward
                pitch  = glm::clamp(pitch, glm::radians(-89.0f),
                                            glm::radians(89.0f));
                break;
            case SDL_EVENT_MOUSE_WHEEL:             // wheel.y is float in SDL3
                fov = glm::clamp(fov - e.wheel.y * 2.0f, 20.0f, 100.0f);
                break;
            default:
                break;
            }
        }

        app.beginFrame();          // refreshes app.dt(), size, viewport

        // ---- movement (frame-rate independent via app.dt()) ----------------
        // Direction from yaw/pitch (yaw = 0 looks down -Z).
        const glm::vec3 front(std::sin(yaw) * std::cos(pitch),
                              std::sin(pitch),
                              -std::cos(yaw) * std::cos(pitch));
        const glm::vec3 right(std::cos(yaw), 0.0f, std::sin(yaw));

        // SDL3 keyboard state is a plain bool array indexed by scancode.
        const bool* keys = SDL_GetKeyboardState(nullptr);
        const float speed =
            (SDL_GetModState() & SDL_KMOD_SHIFT) ? 12.0f : 4.0f;

        if (keys[SDL_SCANCODE_W]) camPos += front * app.dt() * speed;
        if (keys[SDL_SCANCODE_S]) camPos -= front * app.dt() * speed;
        if (keys[SDL_SCANCODE_D]) camPos += right * app.dt() * speed;
        if (keys[SDL_SCANCODE_A]) camPos -= right * app.dt() * speed;
        if (keys[SDL_SCANCODE_E] || keys[SDL_SCANCODE_SPACE])
            camPos.y += speed * app.dt();
        if (keys[SDL_SCANCODE_Q] || keys[SDL_SCANCODE_LCTRL])
            camPos.y -= speed * app.dt();

        // ---- draw a checkerboard floor of cubes -----------------------------
        const float aspect = app.height > 0
                           ? float(app.width) / float(app.height) : 1.0f;
        const glm::mat4 vp = glm::perspective(glm::radians(fov), aspect,
                                              0.1f, 200.0f)
                           * glm::lookAt(camPos, camPos + front,
                                         glm::vec3(0, 1, 0));

        glClearColor(0.10f, 0.12f, 0.16f, 1.0f);
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);

        shader.use();
        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, checker);
        shader.setInt("uTex", 0);
        shader.setMat4("uVP", vp);

        for (int x = -5; x <= 5; ++x)
            for (int z = -5; z <= 5; ++z) {
                shader.setVec3("uColor",
                    ((x + z) & 1) ? glm::vec3(1.0f) : glm::vec3(0.45f));
                shader.setMat4("uModel",
                    glm::translate(glm::mat4(1.0f), glm::vec3(x, -0.6f, z)));
                cube.draw();
            }

        // One tall reference cube at the center.
        shader.setVec3("uColor", glm::vec3(1.0f, 0.7f, 0.3f));
        shader.setMat4("uModel",
            glm::translate(glm::mat4(1.0f), glm::vec3(0, 0.4f, 0)) *
            glm::scale(glm::mat4(1.0f), glm::vec3(1.0f, 2.0f, 1.0f)));
        cube.draw();

        app.endFrame();
    }

    cube.destroy();
    glDeleteTextures(1, &checker);
    return 0;
}
