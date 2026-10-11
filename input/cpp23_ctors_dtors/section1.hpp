#pragma once
#include "common.hpp"

// =============================================================================
// SECTION 1 — THE RULE OF FIVE
// =============================================================================
// This class owns a raw heap allocation. The compiler-generated defaults would
// do a *shallow* copy → double-free. We MUST define all five special members.
namespace section1 {

class HeapBuffer {
    std::size_t size_;
    int*        data_;

public:
    // 1. Parameterized Constructor
    // Allocates the resource and value-initializes it to zero.
    explicit HeapBuffer(std::size_t n)
        : size_(n), data_(new int[n]{}) {}

    // 2. Destructor — frees the resource
    ~HeapBuffer() {
        delete[] data_;
    }

    // 3. Copy Constructor — deep copy
    // Allocates a new buffer and copies the data. The original is untouched.
    HeapBuffer(const HeapBuffer& o)
        : size_(o.size_), data_(new int[o.size_]) {
        std::copy(o.data_, o.data_ + size_, data_);
    }

    // 4. Copy Assignment — Copy-and-Swap Idiom
    // Pass 'o' by value (invokes copy ctor). If allocation throws, 'this' 
    // is untouched (strong exception guarantee). Swapping is noexcept.
    HeapBuffer& operator=(HeapBuffer o) noexcept {
        std::swap(size_, o.size_);
        std::swap(data_,  o.data_);
        return *this; 
        // 'o' goes out of scope here, calling its destructor to free our OLD data.
    }

    // 5. Move Constructor — steal, leave source empty
    // noexcept is REQUIRED so std::vector will use it during reallocation.
    HeapBuffer(HeapBuffer&& o) noexcept
        : size_(std::exchange(o.size_, 0)),
          data_(std::exchange(o.data_, nullptr)) {}

    // 6. Move Assignment
    // Implemented via swap. The temporary 'o' cleans up our old state.
    HeapBuffer& operator=(HeapBuffer&& o) noexcept {
        std::swap(size_, o.size_);
        std::swap(data_,  o.data_);
        return *this;
    }

    [[nodiscard]] std::size_t size() const noexcept { return size_; }
};

inline void run() {
    HeapBuffer a(8);
    HeapBuffer b = a;              // Copy. 'b' has its own allocation.
    HeapBuffer c = std::move(a);   // Move. 'c' steals 'a's pointer. 'a' is now null/0.
    b = c;                         // Copy-assign. Invokes copy ctor, then swaps.
}

} // namespace section1
