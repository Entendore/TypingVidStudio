// =============================================================================
//  10_geometry_shader.cpp - geometry shaders on GL_LINES
// =============================================================================
//  Concepts: the geometry shader stage (runs AFTER the VS, per PRIMITIVE),
//            layout(lines) in / layout(triangle_strip, max_vertices) out,
//            gl_in[] built-in interface, EmitVertex()/EndPrimitive(),
//            expanding 1-pixel lines into screen-space ribbons.
//
//  WHY a GS? glLineWidth(>1) is deprecated and capped at 1.0 by most modern
//  drivers - the only portable way to draw thick lines is to build the quads
//  yourself (GS) or on the CPU. The GS does it per segment with 4 emitted
//  vertices.
//
//  Scene: a pulsing "spark burst" of ~220 radiating line segments, rebuilt
//  every frame into a GL_STREAM_DRAW buffer (dynamic vertex data example).
//  Controls: mouse wheel = ribbon thickness. Esc quits.
// =============================================================================
#include "common/gl_app.hpp"
#include "common/shader.hpp"
#include <cmath>
#include <vector>
#include <cstdio>

// The VS only projects; it stores the clip-space result in gl_Position,
// which the GS reads back through its built-in gl_in[] array.
static const char* VS = R"GLSL(#version 430 core
layout(location = 0) in vec3 aPos;
layout(location = 1) in vec3 aCol;
uniform mat4 uVP;
uniform mat4 uModel;
out vec3 vCol;
void main() {
    vCol = aCol;
    gl_Position = uVP * (uModel * vec4(aPos, 1.0));
}
)GLSL";

static const char* GS = R"GLSL(#version 430 core
layout(lines) in;                              // 2 input vertices / invocation
layout(triangle_strip, max_vertices = 4) out;  // we emit a quad as a strip

in vec3 vCol[];                                // matches the VS 'out'
out vec3 vTint;                                // -> FS, interpolated by HW
out vec2 vUV;                                  // (along, across) the ribbon

uniform float uThickness;   // half ribbon width in NDC units
uniform float uAspect;      // width/height, keeps the width isotropic

void main() {
    // Perspective divide -> NDC. NOTE: expanding AFTER the divide slightly
    // distorts thickness with depth; expanding in clip space is the fully
    // correct (and messier) variant. Also: endpoints behind the camera
    // (w < 0) break this simple math - real engines clip or split first.
    vec3 a = gl_in[0].gl_Position.xyz / gl_in[0].gl_Position.w;
    vec3 b = gl_in[1].gl_Position.xyz / gl_in[1].gl_Position.w;

    // Aspect-corrected 2D direction of the segment...
    vec2 d = vec2((b.x - a.x) * uAspect, b.y - a.y);
    // ...so this perpendicular has unit length in "square" screen space.
    vec2 n = normalize(vec2(-d.y, d.x));
    // Back to NDC: undo the aspect correction on x, scale by thickness.
    vec2 off = vec2(n.x / uAspect, n.y) * uThickness;

    // Emit the 4 quad corners as a triangle strip (order: strip zig-zags).
    // Each corner keeps its endpoint's z, so depth still interpolates,
    // and its endpoint's color -> the ribbon gradients dim -> bright.
    gl_Position = vec4(a.xy - off, a.z, 1.0);  vUV = vec2(0, 0);  vTint = vCol[0];  EmitVertex();
    gl_Position = vec4(b.xy - off, b.z, 1.0);  vUV = vec2(1, 0);  vTint = vCol[1];  EmitVertex();
    gl_Position = vec4(a.xy + off, a.z, 1.0);  vUV = vec2(0, 1);  vTint = vCol[0];  EmitVertex();
    gl_Position = vec4(b.xy + off, b.z, 1.0);  vUV = vec2(1, 1);  vTint = vCol[1];  EmitVertex();
    EndPrimitive();   // finishes the triangle_strip (2 triangles)
}
)GLSL";

static const char* FS = R"GLSL(#version 430 core
in vec3 vTint;
in vec2 vUV;
out vec4 FragColor;
void main() {
    // vUV.y goes 0 -> 1 across the ribbon: fade the long edges to alpha 0
    // for a soft "glow stick" profile (additive blending is enabled).
    float across = abs(vUV.y * 2.0 - 1.0);          // 0 center, 1 edge
    FragColor = vec4(vTint, 1.0 - across * across);
}
)GLSL";

int main() {
    GLApp app;
    if (!app.init("10 - Geometry shader ribbons (wheel = thickness)")) return 1;

    // Shader::build() is VS+FS only, so assemble VS->GS->FS by hand.
    Shader shader;
    {
        GLuint vs = Shader::compile(GL_VERTEX_SHADER, VS);
        GLuint gs = Shader::compile(GL_GEOMETRY_SHADER, GS);
        GLuint fs = Shader::compile(GL_FRAGMENT_SHADER, FS);
        shader.handle = glCreateProgram();
        glAttachShader(shader.handle, vs);
        glAttachShader(shader.handle, gs);   // the new stage sits in between
        glAttachShader(shader.handle, fs);
        glLinkProgram(shader.handle);
        glDeleteShader(vs); glDeleteShader(gs); glDeleteShader(fs);
        GLint ok = GL_FALSE;
        glGetProgramiv(shader.handle, GL_LINK_STATUS, &ok);
        if (!ok) {
            char log[4096];
            glGetProgramInfoLog(shader.handle, sizeof log, nullptr, log);
            std::fprintf(stderr, "Program link error:\n%s\n", log);
            return 1;
        }
    }

    constexpr int RAYS = 220;
    // Per endpoint: position(3) + color(3). Two endpoints per GL_LINES segment.
    std::vector<float> lineData(size_t(RAYS) * 2 * 6);

    GLuint vao = 0, vbo = 0;
    glGenVertexArrays(1, &vao);
    glBindVertexArray(vao);
    glGenBuffers(1, &vbo);
    glBindBuffer(GL_ARRAY_BUFFER, vbo);
    // STREAM_DRAW: rewritten every frame (vs STATIC_DRAW for static geometry).
    glBufferData(GL_ARRAY_BUFFER,
                 GLsizeiptr(lineData.size() * sizeof(float)),
                 nullptr, GL_STREAM_DRAW);
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 6 * sizeof(float),
                          (const void*)0);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 6 * sizeof(float),
                          (const void*)(3 * sizeof(float)));
    glEnableVertexAttribArray(1);
    glBindVertexArray(0);

    // Additive blending: ribbons ADD brightness -> overlapping rays glow.
    // (No depth test: this is a pure 2D-ish light effect on a dark clear.)
    glEnable(GL_BLEND);
    glBlendFunc(GL_SRC_ALPHA, GL_ONE);

    float thickness = 0.012f;

    // Cosine palette: smooth rainbow from a single scalar.
    auto palette = [](float x, float out[3]) {
        out[0] = 0.5f + 0.5f * std::cos(x + 0.0f);
        out[1] = 0.5f + 0.5f * std::cos(x + 2.094f);
        out[2] = 0.5f + 0.5f * std::cos(x + 4.188f);
    };

    bool running = true;
    while (running) {
        SDL_Event e;
        while (SDL_PollEvent(&e)) {
            if (e.type == SDL_EVENT_QUIT) running = false;
            if (e.type == SDL_EVENT_KEY_DOWN &&
                e.key.key == SDLK_ESCAPE) running = false;
            if (e.type == SDL_EVENT_MOUSE_WHEEL) {
                thickness *= (e.wheel.y > 0) ? 1.15f : 1.0f / 1.15f;
                thickness = glm::clamp(thickness, 0.003f, 0.06f);
            }
        }

        app.beginFrame();
        const float t = app.time();
        const float aspect = app.height > 0
                           ? float(app.width) / float(app.height) : 1.0f;

        // ---- rebuild the burst on the CPU (dynamic buffer demo) -------------
        for (int i = 0; i < RAYS; ++i) {
            const float a     = float(i) / RAYS * 6.2831853f + t * 0.15f;
            const float phase = float(i) * 0.618f;          // golden spread
            const float pulse = 0.5f + 0.5f * std::sin(t * 2.0f + phase);
            const float len   = 0.25f + 1.1f * pulse * pulse; // punchy pops
            const float ca = std::cos(a), sa = std::sin(a);
            const float wob = 0.30f * std::sin(t * 0.8f + a * 3.0f);

            float rgb[3];
            palette(a * 1.5f - t * 0.6f, rgb);

            float* v = &lineData[size_t(i) * 12];
            v[0] = 0;        v[1] = 0;       v[2] = 0;    // inner point: origin
            v[3] = rgb[0]*0.12f; v[4] = rgb[1]*0.12f; v[5] = rgb[2]*0.12f;
            v[6] = ca * len; v[7] = sa * len; v[8] = wob; // tip: animated
            v[9] = rgb[0];   v[10] = rgb[1];  v[11] = rgb[2];
        }
        glBindBuffer(GL_ARRAY_BUFFER, vbo);
        glBufferSubData(GL_ARRAY_BUFFER, 0,
                        GLsizeiptr(lineData.size() * sizeof(float)),
                        lineData.data());

        // ---- draw ------------------------------------------------------------
        const glm::mat4 model =
            glm::rotate(glm::mat4(1.0f),
                        std::sin(t * 0.4f) * 0.45f, glm::vec3(1, 0, 0)) *
            glm::rotate(glm::mat4(1.0f), t * 0.25f, glm::vec3(0, 1, 0));
        const glm::mat4 vp = glm::perspective(glm::radians(50.0f), aspect,
                                              0.1f, 100.0f)
                           * glm::translate(glm::mat4(1.0f),
                                            glm::vec3(0, 0, -3.4f));

        glClearColor(0.04f, 0.05f, 0.08f, 1.0f);
        glClear(GL_COLOR_BUFFER_BIT);

        shader.use();
        shader.setMat4("uVP", vp);
        shader.setMat4("uModel", model);
        shader.setFloat("uThickness", thickness);
        shader.setFloat("uAspect", aspect);

        glBindVertexArray(vao);
        // GL_LINES: every consecutive PAIR of vertices is one GS invocation.
        glDrawArrays(GL_LINES, 0, RAYS * 2);

        app.endFrame();
    }

    glDeleteBuffers(1, &vbo);
    glDeleteVertexArrays(1, &vao);
    return 0;
}
