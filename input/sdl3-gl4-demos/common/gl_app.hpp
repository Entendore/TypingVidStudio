#pragma once
// =============================================================================
//  common/gl_app.hpp - SDL3 + OpenGL 4.3 bootstrap shared by all demos
// =============================================================================
//  Header order matters: <glad/gl.h> must be included before any other header
//  that could pull in system OpenGL declarations.
//
//  Extras beyond plain window/context setup:
//    * app.time() / app.dt()   - clock helpers (no per-demo timer boilerplate)
//    * FPS shown in the window title (demos rename the prefix via setBaseTitle)
//    * debug GL context + glDebugMessageCallback: spec violations are printed
//      to stderr instead of silently corrupting state ("black screen" be gone)
//    * GL_CHECK(expr) - immediate glGetError() wrapper for pinpointing errors
// =============================================================================
#include <glad/gl.h>
#include <SDL3/SDL.h>

#include <cstdio>
#include <string>

// -----------------------------------------------------------------------------
//  GL_CHECK(expr) - run a GL call, then check glGetError() immediately.
//  Disabled in release builds (NDEBUG) because glGetError forces a GPU sync.
//      GL_CHECK(glBindTexture(GL_TEXTURE_2D, tex));
// -----------------------------------------------------------------------------
#ifndef NDEBUG
#define GL_CHECK(expr)                                                     \
    do {                                                                   \
        (expr);                                                            \
        const GLenum glErr_ = glGetError();                                \
        if (glErr_ != GL_NO_ERROR)                                         \
            std::fprintf(stderr, "GL error 0x%04X at %s:%d: %s\n",         \
                         glErr_, __FILE__, __LINE__, #expr);               \
    } while (0)
#else
#define GL_CHECK(expr) (expr)
#endif

// Debug-message callback: the driver calls this whenever the app violates the
// GL spec (bad enums, incomplete FBOs, texture-feedback loops, ...). Core
// since GL 4.3. Catching these in a debugger beats staring at a black screen.
inline void GLAPIENTRY glDebugCallback(GLenum /*source*/, GLenum /*type*/,
                                       GLuint id, GLenum severity,
                                       GLsizei length, const GLchar* message,
                                       const void* /*user*/)
{
    // Ignore the two noisiest NVIDIA info messages (buffer usage hints and
    // "static VAO rebind" style notes) so real problems stay visible.
    if (id == 131185 || id == 131169) return;
    if (severity == GL_DEBUG_SEVERITY_NOTIFICATION) return;   // too chatty

    const char* sev = "MESSAGE";
    switch (severity) {
    case GL_DEBUG_SEVERITY_HIGH:   sev = "HIGH";   break;
    case GL_DEBUG_SEVERITY_MEDIUM: sev = "MEDIUM"; break;
    case GL_DEBUG_SEVERITY_LOW:    sev = "LOW";    break;
    }
    std::fprintf(stderr, "[GL %s] id=%u: %.*s\n", sev, id, length, message);
}

struct GLApp {
    SDL_Window*   window  = nullptr;
    SDL_GLContext context = nullptr;
    int width = 1280, height = 720;   // updated every frame (resize / HiDPI)
    float dt = 0.0f;                  // seconds since the previous beginFrame()

    // Clock state (initialized in init()).
    double      frequency_   = 0.0;
    double      prevFrame_   = 0.0;
    double      initTime_    = 0.0;
    double      fpsWindowT0_ = -1.0;
    int         fpsFrames_   = 0;
    std::string baseTitle_;

    ~GLApp() {
        if (context) SDL_GL_DestroyContext(context);  // SDL3 rename (was Delete)
        if (window)  SDL_DestroyWindow(window);
        SDL_Quit();
    }

    // Seconds since init() - the demo animation clock.
    float time() const {
        return float((double(SDL_GetPerformanceCounter()) - initTime_) / frequency_);
    }

    // Change the part of the window title that comes before " | NN FPS".
    void setBaseTitle(const char* t) {
        baseTitle_ = t;
        SDL_SetWindowTitle(window, t);   // immediate feedback...
        fpsWindowT0_ = -1.0;             // ...FPS suffix returns within 0.5 s
    }

    bool init(const char* title, int w = 1280, int h = 720,
              bool debugContext = true) {
        baseTitle_ = title;
        if (!SDL_Init(SDL_INIT_VIDEO)) {              // SDL3: returns bool
            std::fprintf(stderr, "SDL_Init failed: %s\n", SDL_GetError());
            return false;
        }

        // Request an OpenGL 4.3 CORE context (no legacy fixed function).
        // NOTE: macOS caps at 4.1 - demos 07/08/09 need a real 4.3 driver.
        SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 4);
        SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 3);
        SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK,
                            SDL_GL_CONTEXT_PROFILE_CORE);
        SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER, 1);
        // Debug contexts let the driver validate calls and route complaints
        // through the callback below. Slower, but invaluable while learning.
        SDL_GL_SetAttribute(SDL_GL_CONTEXT_FLAGS,
                            debugContext ? int(SDL_GL_CONTEXT_DEBUG_FLAG) : 0);

        // SDL3 signature: (title, w, h, flags) - no x/y position anymore.
        window = SDL_CreateWindow(title, w, h,
                                  SDL_WINDOW_OPENGL | SDL_WINDOW_RESIZABLE);
        if (!window) {
            std::fprintf(stderr, "SDL_CreateWindow failed: %s\n", SDL_GetError());
            return false;
        }

        context = SDL_GL_CreateContext(window);       // also makes it current
        if (!context) {
            std::fprintf(stderr, "SDL_GL_CreateContext failed: %s\n",
                         SDL_GetError());
            return false;
        }
        SDL_GL_SetSwapInterval(1);                    // vsync

        // GLAD2: resolve every gl* entry point through SDL's function loader.
        if (gladLoadGL(reinterpret_cast<GLADloadfunc>(SDL_GL_GetProcAddress)) == 0) {
            std::fprintf(stderr, "gladLoadGL failed\n");
            return false;
        }

        // Print what the driver actually gave us.
        std::printf("GL %s | %s | %s | GLSL %s%s\n",
                    glGetString(GL_VERSION), glGetString(GL_RENDERER),
                    glGetString(GL_VENDOR),
                    glGetString(GL_SHADING_LANGUAGE_VERSION),
                    debugContext ? " (debug context)" : "");

        // Hook up debug output (core in 4.3; guard for exotic setups anyway).
        if (glDebugMessageCallback) {
            glEnable(GL_DEBUG_OUTPUT);
            // SYNCHRONOUS: the callback fires *during* the offending call, so
            // a breakpoint lands on the real culprit. Slow - debug builds only.
            glEnable(GL_DEBUG_OUTPUT_SYNCHRONOUS);
            glDebugMessageCallback(glDebugCallback, nullptr);
        }

        frequency_   = double(SDL_GetPerformanceFrequency());
        initTime_    = double(SDL_GetPerformanceCounter());
        prevFrame_   = initTime_;
        return true;
    }

    // Updates dt, backbuffer size and viewport. Call once per frame, first.
    void beginFrame() {
        const double now = double(SDL_GetPerformanceCounter());
        dt = float((now - prevFrame_) / frequency_);
        if (dt > 0.25f) dt = 0.25f;   // clamp stalls (breakpoints, tab-outs)
        prevFrame_ = now;
        SDL_GetWindowSizeInPixels(window, &width, &height);
        glViewport(0, 0, width, height);
    }

    // Presents the frame and refreshes the " | NN FPS" title ~2x per second.
    void endFrame() {
        SDL_GL_SwapWindow(window);
        ++fpsFrames_;
        const double now = double(SDL_GetPerformanceCounter()) / frequency_;
        if (fpsWindowT0_ < 0.0) fpsWindowT0_ = now;
        const double elapsed = now - fpsWindowT0_;
        if (elapsed >= 0.5) {
            char buf[256];
            std::snprintf(buf, sizeof buf, "%s | %d FPS", baseTitle_.c_str(),
                          int(double(fpsFrames_) / elapsed + 0.5));
            SDL_SetWindowTitle(window, buf);
            fpsFrames_   = 0;
            fpsWindowT0_ = now;
        }
    }
};
