#pragma once
// =============================================================================
//  common/texture.hpp - textures generated on the CPU / on the GPU
// =============================================================================
#include <glad/gl.h>
#include <cstdint>
#include <vector>

// CPU-generated RGBA checkerboard (a stand-in for stb_image-loaded files).
inline GLuint makeCheckerTexture(int size, int cells, bool mipmaps = true)
{
    std::vector<std::uint8_t> px(std::size_t(size) * size * 4);
    for (int y = 0; y < size; ++y)
        for (int x = 0; x < size; ++x) {
            const bool on = ((x * cells) / size + (y * cells) / size) & 1;
            const std::uint8_t v = on ? 235 : 45;
            auto* p = &px[(std::size_t(y) * size + x) * 4];
            p[0] = v; p[1] = v; p[2] = v; p[3] = 255;
        }

    GLuint tex = 0;
    glGenTextures(1, &tex);
    glBindTexture(GL_TEXTURE_2D, tex);

    // Wrap mode: UVs outside [0,1] repeat (tiles). Filter: mipmaps give
    // smooth minification instead of shimmery aliasing at a distance.
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_REPEAT);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_REPEAT);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER,
                    mipmaps ? GL_LINEAR_MIPMAP_LINEAR : GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);

    glPixelStorei(GL_UNPACK_ALIGNMENT, 1);
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, size, size, 0,
                 GL_RGBA, GL_UNSIGNED_BYTE, px.data());
    if (mipmaps)
        glGenerateMipmap(GL_TEXTURE_2D);          // build mip chain on the GPU
    return tex;
}

// Empty *immutable-storage* texture - used as an FBO color attachment or as
// the target of a compute-shader imageStore (immutable storage is the
// recommended/reliable layout for image units).
inline GLuint makeEmptyTexture(GLsizei w, GLsizei h, GLenum internalFormat)
{
    GLuint tex = 0;
    glGenTextures(1, &tex);
    glBindTexture(GL_TEXTURE_2D, tex);
    glTexStorage2D(GL_TEXTURE_2D, 1, internalFormat, w, h);  // 1 mip level
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
    return tex;
}
