#pragma once
// =============================================================================
//  common/shader.hpp - minimal shader program wrapper
// =============================================================================
#include <glad/gl.h>
#include <glm/glm.hpp>
#include <glm/gtc/type_ptr.hpp>
#include <cstdio>
#include <cstdlib>

struct Shader {
    GLuint handle = 0;

    // Compile one stage; abort with the driver's info log on failure.
    static GLuint compile(GLenum stage, const char* src) {
        GLuint s = glCreateShader(stage);
        glShaderSource(s, 1, &src, nullptr);
        glCompileShader(s);
        GLint ok = GL_FALSE;
        glGetShaderiv(s, GL_COMPILE_STATUS, &ok);
        if (!ok) {
            char log[4096];
            glGetShaderInfoLog(s, sizeof log, nullptr, log);
            std::fprintf(stderr, "Shader compile error:\n%s\n", log);
            std::exit(1);
        }
        return s;
    }

    // Build a program from a vertex + fragment source pair.
    void build(const char* vsSrc, const char* fsSrc) {
        GLuint vs = compile(GL_VERTEX_SHADER, vsSrc);
        GLuint fs = compile(GL_FRAGMENT_SHADER, fsSrc);
        handle = glCreateProgram();
        glAttachShader(handle, vs);
        glAttachShader(handle, fs);
        glLinkProgram(handle);
        glDeleteShader(vs);   // safe: freed together with the program
        glDeleteShader(fs);

        GLint ok = GL_FALSE;
        glGetProgramiv(handle, GL_LINK_STATUS, &ok);
        if (!ok) {
            char log[4096];
            glGetProgramInfoLog(handle, sizeof log, nullptr, log);
            std::fprintf(stderr, "Program link error:\n%s\n", log);
            std::exit(1);
        }
    }

    void  use() const { glUseProgram(handle); }
    GLint loc(const char* n) const { return glGetUniformLocation(handle, n); }

    // Uniform setters. location == -1 ("optimized out") is silently ignored.
    void setMat4(const char* n, const glm::mat4& m) const {
        glUniformMatrix4fv(loc(n), 1, GL_FALSE, glm::value_ptr(m));
    }
    void setVec3(const char* n, const glm::vec3& v) const {
        glUniform3f(loc(n), v.x, v.y, v.z);
    }
    void setFloat(const char* n, float f) const { glUniform1f(loc(n), f); }
    void setInt  (const char* n, int i)   const { glUniform1i(loc(n), i); }
};
