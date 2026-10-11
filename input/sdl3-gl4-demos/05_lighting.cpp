// =============================================================================
//  05_lighting.cpp - Blinn-Phong lighting
// =============================================================================
//  Concepts: per-fragment lighting, normals & the normal matrix, ambient/
//            diffuse/specular terms, distance attenuation, emissive light
//            source rendered as its own (unlit) object.
// =============================================================================
#include "common/gl_app.hpp"
#include "common/shader.hpp"
#include "common/geometry.hpp"
#include <cmath>

// --- lit object shader -------------------------------------------------------
static const char* OBJ_VS = R"GLSL(#version 430 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;
uniform mat4 uModel;
uniform mat4 uVP;
out vec3 vNormal;
out vec3 vWorldPos;
void main() {
    vec4 world = uModel * vec4(aPos, 1.0);
    vWorldPos = world.xyz;
    // Normal matrix: normals are directions, not positions - transform them
    // by inverse-transpose(model) so non-uniform scaling can't skew them.
    vNormal = mat3(transpose(inverse(uModel))) * aNormal;
    gl_Position = uVP * world;
}
)GLSL";

static const char* OBJ_FS = R"GLSL(#version 430 core
in vec3 vNormal;
in vec3 vWorldPos;
out vec4 FragColor;
uniform vec3 uViewPos;      // camera position (for the specular term)
uniform vec3 uLightPos;
uniform vec3 uLightColor;
uniform vec3 uColor;        // object's albedo
void main() {
    // Ambient: faked constant bounce light so nothing is pitch black.
    vec3 ambient = 0.12f * uLightColor;

    // Diffuse (Lambert): brightness = max(N.L, 0).
    vec3 N = normalize(vNormal);
    vec3 L = normalize(uLightPos - vWorldPos);
    float diff = max(dot(N, L), 0.0f);

    // Specular (Blinn-Phong): highlight around the half vector, sharper
    // and cheaper than classic Phong reflection.
    vec3 V = normalize(uViewPos - vWorldPos);
    vec3 H = normalize(L + V);
    float spec = pow(max(dot(N, H), 0.0f), 64.0f);

    // Distance attenuation so the orbiting light visibly "breathes".
    float dist  = length(uLightPos - vWorldPos);
    float atten = 1.0f / (1.0f + 0.14f * dist + 0.07f * dist * dist);

    vec3 color = (ambient + (diff + 0.6f * spec) * uLightColor * atten)
               * uColor;
    FragColor = vec4(color, 1.0f);
}
)GLSL";

// --- light source shader (unlit / emissive) ----------------------------------
static const char* LIGHT_VS = R"GLSL(#version 430 core
layout(location = 0) in vec3 aPos;    // normal attribute exists but is unused
uniform mat4 uModel;
uniform mat4 uVP;
void main() { gl_Position = uVP * (uModel * vec4(aPos, 1.0)); }
)GLSL";

static const char* LIGHT_FS = R"GLSL(#version 430 core
uniform vec3 uLightColor;
out vec4 FragColor;
void main() { FragColor = vec4(uLightColor, 1.0); }
)GLSL";

int main() {
    GLApp app;
    if (!app.init("05 - Blinn-Phong lighting")) return 1;

    Shader obj, light;
    obj.build(OBJ_VS, OBJ_FS);
    light.build(LIGHT_VS, LIGHT_FS);
    const Mesh cube = makeCubeMesh();

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

        const glm::vec3 camPos(0.0f, 2.2f, 5.5f);
        const glm::mat4 vp = glm::perspective(glm::radians(50.0f), aspect,
                                              0.1f, 100.0f)
                           * glm::lookAt(camPos, glm::vec3(0),
                                         glm::vec3(0, 1, 0));

        // The light orbits and bobs; the small emissive cube marks its spot.
        const glm::vec3 lightPos(2.6f * std::sin(t * 0.8f),
                                 1.6f + 0.6f * std::sin(t * 1.7f),
                                 2.6f * std::cos(t * 0.8f));
        const glm::vec3 lightColor(1.0f, 0.95f, 0.85f);

        glClearColor(0.07f, 0.08f, 0.11f, 1.0f);
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);

        // ---- lit objects ----------------------------------------------------
        obj.use();
        obj.setMat4("uVP", vp);
        obj.setVec3("uViewPos", camPos);
        obj.setVec3("uLightPos", lightPos);
        obj.setVec3("uLightColor", lightColor);

        struct { glm::mat4 m; glm::vec3 c; } items[] = {
            // big center cube, slowly rotating
            { glm::rotate(glm::mat4(1.0f), t * 0.6f,
                          glm::vec3(0.3f, 1.0f, 0.1f)),
              glm::vec3(0.8f, 0.35f, 0.3f) },
            // two satellites
            { glm::translate(glm::mat4(1.0f), glm::vec3(-1.9f, -0.3f, 0.4f)) *
              glm::scale(glm::mat4(1.0f), glm::vec3(0.6f)),
              glm::vec3(0.3f, 0.55f, 0.9f) },
            { glm::translate(glm::mat4(1.0f), glm::vec3(1.8f, 0.7f, -0.6f)) *
              glm::scale(glm::mat4(1.0f), glm::vec3(0.5f)) *
              glm::rotate(glm::mat4(1.0f), t, glm::vec3(0, 1, 0)),
              glm::vec3(0.35f, 0.8f, 0.45f) },
        };
        for (const auto& it : items) {
            obj.setMat4("uModel", it.m);
            obj.setVec3("uColor", it.c);
            cube.draw();
        }

        // ---- the light source itself (drawn last, unlit) --------------------
        light.use();
        light.setMat4("uVP", vp);
        light.setMat4("uModel",
            glm::translate(glm::mat4(1.0f), lightPos) *
            glm::scale(glm::mat4(1.0f), glm::vec3(0.15f)));
        light.setVec3("uLightColor", lightColor);
        cube.draw();

        app.endFrame();
    }

    cube.destroy();
    return 0;
}
