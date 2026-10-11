// =============================================================================
//  07_compute.cpp - compute shaders (requires a real OpenGL 4.3+ context)
// =============================================================================
//  Concepts: compute programs & workgroups, image units (imageStore),
//            glMemoryBarrier to publish results, and "attribute-less"
//            rendering where the fullscreen triangle is generated from
//            gl_VertexID - no vertex buffers at all.
// =============================================================================
#include "common/gl_app.hpp"
#include "common/shader.hpp"
#include "common/texture.hpp"

// --- compute stage: one invocation per pixel ---------------------------------
static const char* CS = R"GLSL(#version 430 core
// Workgroup shape: 16x16 invocations share local memory/scheduling.
layout(local_size_x = 16, local_size_y = 16) in;
// 'binding' here is the IMAGE unit (not a texture unit), rgba32f must match
// the texture's internal format exactly.
layout(rgba32f, binding = 0) writeonly uniform image2D uImage;
uniform float uTime;
uniform vec2  uSize;
void main() {
    ivec2 pix = ivec2(gl_GlobalInvocationID.xy);   // global id = our pixel
    vec2 uv = (vec2(pix) + 0.5) / uSize * 2.0 - 1.0;

    // Classic plasma: sums of sines in space and time.
    float v = sin(uv.x * 8.0 + uTime)
            + sin(uv.y * 8.0 - uTime * 1.3)
            + sin(length(uv) * 12.0 - uTime * 2.0)
            + sin(atan(uv.y, uv.x) * 4.0 + uTime * 0.7);

    // Map to a rainbow via phase-shifted cosines.
    vec3 col = 0.5 + 0.5 * cos(v + vec3(0.0, 2.094, 4.188));
    imageStore(uImage, pix, vec4(col, 1.0));
}
)GLSL";

// --- display pass: fullscreen triangle with NO vertex data -------------------
static const char* VS = R"GLSL(#version 430 core
out vec2 vUV;
void main() {
    // gl_VertexID picks the corner: (-1,-1), (3,-1), (-1,3) covers the
    // whole screen with a single oversized triangle. Zero attributes!
    vec2 p = vec2(gl_VertexID == 1 ? 3.0 : -1.0,
                  gl_VertexID == 2 ? 3.0 : -1.0);
    gl_Position = vec4(p, 0.0, 1.0);
    vUV = p * 0.5 + 0.5;
}
)GLSL";

static const char* FS = R"GLSL(#version 430 core
in vec2 vUV;
out vec4 FragColor;
uniform sampler2D uTex;    // reads back what the compute shader wrote
void main() { FragColor = texture(uTex, vUV); }
)GLSL";

int main() {
    GLApp app;
    if (!app.init("07 - Compute shader plasma")) return 1;

    // Compute programs have NO vertex/fragment stages - build one directly.
    // (Shader::build() always attaches VS+FS, which is wrong for compute.)
    Shader compute;
    {
        GLuint cs = Shader::compile(GL_COMPUTE_SHADER, CS);
        compute.handle = glCreateProgram();
        glAttachShader(compute.handle, cs);
        glLinkProgram(compute.handle);
        glDeleteShader(cs);
        GLint ok = GL_FALSE;
        glGetProgramiv(compute.handle, GL_LINK_STATUS, &ok);
        if (!ok) {
            char log[4096];
            glGetProgramInfoLog(compute.handle, sizeof log, nullptr, log);
            std::fprintf(stderr, "Compute link error:\n%s\n", log);
            return 1;
        }
    }

    Shader display;
    display.build(VS, FS);

    constexpr int TEX = 512;
    const GLuint tex = makeEmptyTexture(TEX, TEX, GL_RGBA32F);

    // Core profile gotcha: a draw call requires SOME VAO to be bound, even
    // when the shader uses no attributes at all. So make an empty one.
    GLuint emptyVao = 0;
    glGenVertexArrays(1, &emptyVao);

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

        // ---- PASS 1: compute - fill the texture -----------------------------
        compute.use();
        glBindImageTexture(0, tex, 0, GL_FALSE, 0, GL_WRITE_ONLY, GL_RGBA32F);
        compute.setFloat("uTime", t);
        glUniform2f(compute.loc("uSize"), float(TEX), float(TEX));
        // Dispatch enough 16x16 workgroups to cover 512x512 pixels: 32x32.
        glDispatchCompute((TEX + 15) / 16, (TEX + 15) / 16, 1);
        // Guarantee the image writes are visible to the sampling pass below.
        glMemoryBarrier(GL_SHADER_IMAGE_ACCESS_BARRIER_BIT |
                        GL_TEXTURE_FETCH_BARRIER_BIT);

        // ---- PASS 2: draw the texture to the screen -------------------------
        glClearColor(0, 0, 0, 1);
        glClear(GL_COLOR_BUFFER_BIT);
        display.use();
        glActiveTexture(GL_TEXTURE0);
        glBindTexture(GL_TEXTURE_2D, tex);
        display.setInt("uTex", 0);
        glBindVertexArray(emptyVao);
        glDrawArrays(GL_TRIANGLES, 0, 3);   // fullscreen triangle

        app.endFrame();
    }

    glDeleteVertexArrays(1, &emptyVao);
    glDeleteTextures(1, &tex);
    return 0;
}
