// =============================================================================
//  09_shadows.cpp - shadow mapping (two passes, one depth texture)
// =============================================================================
//  Concepts: a DEPTH texture as FBO attachment, rendering the scene from the
//            light's point of view, projecting fragments into light space,
//            slope-scaled bias against "shadow acne", percentage-closer
//            filtering (PCF) for soft edges, CLAMP_TO_BORDER so that regions
//            outside the light frustum stay lit.
//
//  PASS 1: render the scene's depth into a 2048x2048 depth texture, using an
//          orthographic light matrix (a directional "sun" light).
//  PASS 2: render normally; each fragment converts its world position into
//          the light's texture space and asks: "am I farther from the light
//          than whatever is stored in the shadow map?" If yes -> in shadow.
//
//  Controls: M toggles a debug view of the raw shadow map. Esc quits.
// =============================================================================
#include "common/gl_app.hpp"
#include "common/shader.hpp"
#include "common/geometry.hpp"
#include <cmath>
#include <cstdio>

// --- PASS 1: depth only. FS body is empty - gl_Position is all we need. ------
static const char* DEPTH_VS = R"GLSL(#version 430 core
layout(location = 0) in vec3 aPos;
uniform mat4 uLightVP;              // ortho light projection * light view
uniform mat4 uModel;
void main() { gl_Position = uLightVP * (uModel * vec4(aPos, 1.0)); }
)GLSL";

static const char* DEPTH_FS = R"GLSL(#version 430 core
void main() { }                     // nothing to write - depth happens anyway
)GLSL";

// --- PASS 2: lit shader with shadow lookup ------------------------------------
static const char* OBJ_VS = R"GLSL(#version 430 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aNormal;
uniform mat4 uModel;
uniform mat4 uVP;
uniform mat4 uLightVP;              // MUST be the exact same matrix as pass 1!
out vec3 vNormal;
out vec3 vWorldPos;
out vec4 vLightClip;                // fragment position in light clip space
void main() {
    vec4 world = uModel * vec4(aPos, 1.0);
    vWorldPos = world.xyz;
    vNormal    = mat3(transpose(inverse(uModel))) * aNormal;
    vLightClip = uLightVP * world;  // project into the light's "camera"
    gl_Position = uVP * world;
}
)GLSL";

static const char* OBJ_FS = R"GLSL(#version 430 core
in vec3 vNormal;
in vec3 vWorldPos;
in vec4 vLightClip;
out vec4 FragColor;
uniform sampler2D uShadowMap;
uniform vec3 uViewPos;
uniform vec3 uLightPos;
uniform vec3 uColor;
uniform int  uVisualize;            // 1 = paint the raw shadow map (debug)

// 3x3 percentage-closer filtering: average 9 depth tests around the fragment
// to soften the hard, shimmering edge a single test would produce.
float shadowFactor(vec3 N, vec3 L)
{
    // Perspective divide, then NDC [-1,1] -> UV [0,1] (the same remap that
    // glViewport applies). proj.z = this fragment's depth from the light.
    vec3 proj = vLightClip.xyz / vLightClip.w;
    proj = proj * 0.5 + 0.5;

    if (proj.z > 1.0)
        return 0.0;                  // behind the light's far plane: lit

    // Slope-scaled bias: the more the surface grazes the light direction,
    // the bigger the depth offset needed - otherwise a surface "shadows
    // itself" and you get dark moire stripes called SHADOW ACNE.
    float bias = max(0.003 * (1.0 - dot(N, L)), 0.0008);

    float shadow = 0.0;
    for (int x = -1; x <= 1; ++x)
        for (int y = -1; y <= 1; ++y) {
            float occluder = texture(uShadowMap,
                                     proj.xy + vec2(x, y) / 2048.0).r;
            shadow += (proj.z - bias > occluder) ? 1.0 : 0.0;
        }
    return shadow / 9.0;             // 0 = fully lit, 1 = fully shadowed
}

void main()
{
    // Debug view: dump the shadow map depths as grayscale (press M).
    if (uVisualize == 1) {
        vec3 proj = vLightClip.xyz / vLightClip.w * 0.5 + 0.5;
        FragColor = vec4(vec3(texture(uShadowMap, proj.xy).r), 1.0);
        return;
    }

    vec3 N = normalize(vNormal);
    vec3 L = normalize(uLightPos - vWorldPos);
    vec3 V = normalize(uViewPos - vWorldPos);
    vec3 H = normalize(L + V);

    float diffuse  = max(dot(N, L), 0.0);
    float specular = pow(max(dot(N, H), 0.0), 32.0);
    float shadow   = shadowFactor(N, L);

    // Ambient light survives in shadow; direct light is blocked by (1-shadow).
    vec3 lit = uColor * (0.15 + (1.0 - shadow) * (0.85 * diffuse + 0.4 * specular));
    FragColor = vec4(lit, 1.0);
}
)GLSL";

int main() {
    GLApp app;
    if (!app.init("09 - Shadow mapping (M = view shadow map)")) return 1;

    Shader depthShader, objShader;
    depthShader.build(DEPTH_VS, DEPTH_FS);
    objShader.build(OBJ_VS, OBJ_FS);
    const Mesh cube = makeCubeMesh();

    glEnable(GL_DEPTH_TEST);
    glEnable(GL_CULL_FACE);

    // ---- 1. The shadow map: a depth texture we render INTO -------------------
    constexpr GLsizei SHADOW_SIZE = 2048;
    GLuint shadowTex = 0;
    glGenTextures(1, &shadowTex);
    glBindTexture(GL_TEXTURE_2D, shadowTex);
    // Float depth for precision. We only ALLOCATE here; pass 1 fills it.
    glTexImage2D(GL_TEXTURE_2D, 0, GL_DEPTH_COMPONENT32F,
                 SHADOW_SIZE, SHADOW_SIZE, 0,
                 GL_DEPTH_COMPONENT, GL_FLOAT, nullptr);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
    // Sampling outside the light frustum returns 1.0 ("no occluder") -> lit.
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_BORDER);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_BORDER);
    const float border[4] = { 1.0f, 1.0f, 1.0f, 1.0f };
    glTexParameterfv(GL_TEXTURE_2D, GL_TEXTURE_BORDER_COLOR, border);

    // Depth-only FBO: NO color attachment at all.
    GLuint shadowFbo = 0;
    glGenFramebuffers(1, &shadowFbo);
    glBindFramebuffer(GL_FRAMEBUFFER, shadowFbo);
    glFramebufferTexture2D(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT,
                           GL_TEXTURE_2D, shadowTex, 0);
    glDrawBuffer(GL_NONE);           // this pass produces no color output
    glReadBuffer(GL_NONE);
    if (glCheckFramebufferStatus(GL_FRAMEBUFFER) != GL_FRAMEBUFFER_COMPLETE) {
        std::fprintf(stderr, "Shadow FBO incomplete!\n");
        return 1;
    }
    glBindFramebuffer(GL_FRAMEBUFFER, 0);

    bool visualize = false;

    // The same geometry is drawn in both passes - the depth comparison in
    // pass 2 only works if both passes use IDENTICAL light matrices.
    auto drawScene = [&](Shader& sh, float tt) {
        // Ground: a large, very flat cube (reuses our Mesh layout).
        sh.setMat4("uModel",
            glm::translate(glm::mat4(1.0f), glm::vec3(0, -0.55f, 0)) *
            glm::scale (glm::mat4(1.0f), glm::vec3(7.0f, 0.1f, 7.0f)));
        sh.setVec3("uColor", glm::vec3(0.55f));
        cube.draw();

        // Center cube, slowly tumbling.
        sh.setMat4("uModel",
            glm::translate(glm::mat4(1.0f), glm::vec3(0, 0.25f, 0)) *
            glm::rotate (glm::mat4(1.0f), tt * 0.7f,
                         glm::vec3(0.4f, 1.0f, 0.2f)));
        sh.setVec3("uColor", glm::vec3(0.85f, 0.4f, 0.3f));
        cube.draw();

        // Orbiting cube.
        sh.setMat4("uModel",
            glm::translate(glm::mat4(1.0f),
                glm::vec3(1.9f * std::cos(tt * 1.1f), 0.9f,
                          1.9f * std::sin(tt * 1.1f))) *
            glm::scale(glm::mat4(1.0f), glm::vec3(0.45f)));
        sh.setVec3("uColor", glm::vec3(0.3f, 0.55f, 0.95f));
        cube.draw();

        // Static cube resting on the ground.
        sh.setMat4("uModel",
            glm::translate(glm::mat4(1.0f), glm::vec3(-1.6f, -0.1f, 0.9f)) *
            glm::scale (glm::mat4(1.0f), glm::vec3(0.7f)) *
            glm::rotate(glm::mat4(1.0f), 0.6f, glm::vec3(0, 1, 0)));
        sh.setVec3("uColor", glm::vec3(0.35f, 0.8f, 0.45f));
        cube.draw();
    };

    bool running = true;
    while (running) {
        SDL_Event e;
        while (SDL_PollEvent(&e)) {
            if (e.type == SDL_EVENT_QUIT) running = false;
            if (e.type == SDL_EVENT_KEY_DOWN) {
                if (e.key.key == SDLK_ESCAPE) running = false;
                if (e.key.key == SDLK_M) {          // toggle shadow-map view
                    visualize = !visualize;
                    app.setBaseTitle(visualize
                        ? "09 - Shadow map debug view (M = back)"
                        : "09 - Shadow mapping (M = view shadow map)");
                }
            }
        }

        app.beginFrame();
        const float t = app.time();
        const float aspect = app.height > 0
                           ? float(app.width) / float(app.height) : 1.0f;

        // The "sun" orbits the scene, so the shadows sweep around.
        const glm::vec3 lightPos(4.5f * std::cos(t * 0.4f), 5.5f,
                                 4.5f * std::sin(t * 0.4f));

        // Orthographic projection = directional light. The ortho box must
        // cover every caster AND receiver, or they fall outside the map
        // (where the border color says "lit").
        const glm::mat4 lightVP =
            glm::ortho(-7.0f, 7.0f, -7.0f, 7.0f, 1.0f, 20.0f) *
            glm::lookAt(lightPos, glm::vec3(0.0f), glm::vec3(0, 1, 0));

        const glm::vec3 camPos(0.0f, 4.2f, 8.5f);
        const glm::mat4 vp =
            glm::perspective(glm::radians(50.0f), aspect, 0.1f, 100.0f) *
            glm::lookAt(camPos, glm::vec3(0.0f), glm::vec3(0, 1, 0));

        // ---- PASS 1: depth from the light's point of view -------------------
        glBindFramebuffer(GL_FRAMEBUFFER, shadowFbo);
        glViewport(0, 0, SHADOW_SIZE, SHADOW_SIZE);   // viewport = map size!
        glClear(GL_DEPTH_BUFFER_BIT);
        // Render BACK faces into the map: pushes occluders slightly "deeper",
        // which reduces acne on lit front faces. (glPolygonOffset(1,1) is the
        // more general modern alternative - left as an exercise!)
        glCullFace(GL_FRONT);
        depthShader.use();
        depthShader.setMat4("uLightVP", lightVP);
        drawScene(depthShader, t);
        glCullFace(GL_BACK);

        // ---- PASS 2: normal draw, sampling the shadow map -------------------
        glBindFramebuffer(GL_FRAMEBUFFER, 0);
        glViewport(0, 0, app.width, app.height);      // back to window size
        glClearColor(0.08f, 0.09f, 0.12f, 1.0f);
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT);

        objShader.use();
        objShader.setMat4("uVP", vp);
        objShader.setMat4("uLightVP", lightVP);       // SAME matrix as pass 1
        objShader.setVec3("uViewPos", camPos);
        objShader.setVec3("uLightPos", lightPos);
        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, shadowTex);
        objShader.setInt("uShadowMap", 0);
        objShader.setInt("uVisualize", visualize ? 1 : 0);
        drawScene(objShader, t);

        app.endFrame();
    }

    glDeleteFramebuffers(1, &shadowFbo);
    glDeleteTextures(1, &shadowTex);
    cube.destroy();
    return 0;
}
