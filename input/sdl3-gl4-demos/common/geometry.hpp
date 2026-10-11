#pragma once
// =============================================================================
//  common/geometry.hpp - a proper lit cube + a small VAO/VBO/EBO helper
// =============================================================================
#include <glad/gl.h>

// 24 vertices (4 per face): vertices at edges are duplicated so each face
// carries its own flat normal - that is what makes hard edges shade correctly.
// Layout per vertex: position(3) + normal(3) + uv(2) = 8 floats.
static const float CUBE_VERTICES[] = {
    //   position            normal             uv
    // +Z front
    -0.5f,-0.5f, 0.5f,   0.0f, 0.0f, 1.0f,   0.0f,0.0f,
     0.5f,-0.5f, 0.5f,   0.0f, 0.0f, 1.0f,   1.0f,0.0f,
     0.5f, 0.5f, 0.5f,   0.0f, 0.0f, 1.0f,   1.0f,1.0f,
    -0.5f, 0.5f, 0.5f,   0.0f, 0.0f, 1.0f,   0.0f,1.0f,
    // -Z back
     0.5f,-0.5f,-0.5f,   0.0f, 0.0f,-1.0f,   0.0f,0.0f,
    -0.5f,-0.5f,-0.5f,   0.0f, 0.0f,-1.0f,   1.0f,0.0f,
    -0.5f, 0.5f,-0.5f,   0.0f, 0.0f,-1.0f,   1.0f,1.0f,
     0.5f, 0.5f,-0.5f,   0.0f, 0.0f,-1.0f,   0.0f,1.0f,
    // +Y top
    -0.5f, 0.5f, 0.5f,   0.0f, 1.0f, 0.0f,   0.0f,0.0f,
     0.5f, 0.5f, 0.5f,   0.0f, 1.0f, 0.0f,   1.0f,0.0f,
     0.5f, 0.5f,-0.5f,   0.0f, 1.0f, 0.0f,   1.0f,1.0f,
    -0.5f, 0.5f,-0.5f,   0.0f, 1.0f, 0.0f,   0.0f,1.0f,
    // -Y bottom
    -0.5f,-0.5f,-0.5f,   0.0f,-1.0f, 0.0f,   0.0f,0.0f,
     0.5f,-0.5f,-0.5f,   0.0f,-1.0f, 0.0f,   1.0f,0.0f,
     0.5f,-0.5f, 0.5f,   0.0f,-1.0f, 0.0f,   1.0f,1.0f,
    -0.5f,-0.5f, 0.5f,   0.0f,-1.0f, 0.0f,   0.0f,1.0f,
    // +X right
     0.5f,-0.5f, 0.5f,   1.0f, 0.0f, 0.0f,   0.0f,0.0f,
     0.5f,-0.5f,-0.5f,   1.0f, 0.0f, 0.0f,   1.0f,0.0f,
     0.5f, 0.5f,-0.5f,   1.0f, 0.0f, 0.0f,   1.0f,1.0f,
     0.5f, 0.5f, 0.5f,   1.0f, 0.0f, 0.0f,   0.0f,1.0f,
    // -X left
    -0.5f,-0.5f,-0.5f,  -1.0f, 0.0f, 0.0f,   0.0f,0.0f,
    -0.5f,-0.5f, 0.5f,  -1.0f, 0.0f, 0.0f,   1.0f,0.0f,
    -0.5f, 0.5f, 0.5f,  -1.0f, 0.0f, 0.0f,   1.0f,1.0f,
    -0.5f, 0.5f,-0.5f,  -1.0f, 0.0f, 0.0f,   0.0f,1.0f,
};

// 6 indices per face. Triangles wind CCW seen from outside (GL's default
// "front face"), which is what backface culling expects.
static const GLuint CUBE_INDICES[] = {
     0, 1, 2,   0, 2, 3,    // front
     4, 5, 6,   4, 6, 7,    // back
     8, 9,10,   8,10,11,    // top
    12,13,14,  12,14,15,    // bottom
    16,17,18,  16,18,19,    // right
    20,21,22,  20,21,23,    // left
};

struct Mesh {
    GLuint  vao = 0, vbo = 0, ebo = 0;
    GLsizei indexCount = 0;

    void draw() const {
        glBindVertexArray(vao);
        glDrawElements(GL_TRIANGLES, indexCount, GL_UNSIGNED_INT, nullptr);
    }
    void destroy() const {
        glDeleteVertexArrays(1, &vao);
        glDeleteBuffers(1, &vbo);
        glDeleteBuffers(1, &ebo);
    }
};

// Uploads interleaved data and enables standard attributes:
//   location 0 = position (3 floats)
//   location 1 = normal   (3 floats, when strideFloats >= 6)
//   location 2 = uv       (2 floats, when strideFloats >= 8)
inline Mesh makeMesh(const float* verts, GLsizeiptr vertBytes,
                     const GLuint* idx,  GLsizeiptr idxBytes,
                     GLsizei count, int strideFloats)
{
    Mesh m;
    m.indexCount = count;
    const GLsizei stride = GLsizei(strideFloats * sizeof(float));

    glGenVertexArrays(1, &m.vao);
    glBindVertexArray(m.vao);

    glGenBuffers(1, &m.vbo);
    glBindBuffer(GL_ARRAY_BUFFER, m.vbo);
    glBufferData(GL_ARRAY_BUFFER, vertBytes, verts, GL_STATIC_DRAW);

    glGenBuffers(1, &m.ebo);                       // EBO state is captured
    glBindBuffer(GL_ELEMENT_ARRAY_BUFFER, m.ebo);  // by the bound VAO!
    glBufferData(GL_ELEMENT_ARRAY_BUFFER, idxBytes, idx, GL_STATIC_DRAW);

    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, stride, (const void*)0);
    glEnableVertexAttribArray(0);
    if (strideFloats >= 6) {
        glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, stride,
                              (const void*)(3 * sizeof(float)));
        glEnableVertexAttribArray(1);
    }
    if (strideFloats >= 8) {
        glVertexAttribPointer(2, 2, GL_FLOAT, GL_FALSE, stride,
                              (const void*)(6 * sizeof(float)));
        glEnableVertexAttribArray(2);
    }
    glBindVertexArray(0);
    return m;
}

inline Mesh makeCubeMesh() {
    return makeMesh(CUBE_VERTICES, sizeof CUBE_VERTICES,
                    CUBE_INDICES,  sizeof CUBE_INDICES, 36, 8);
}
