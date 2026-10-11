#pragma once
#include "common.hpp"

// =============================================================================
// SECTION 8 — MEMBER INITIALIZATION ORDER GOTCHA
// =============================================================================
// KEY RULE: Members are initialized in DECLARATION ORDER, regardless of the
// order you write them in the initializer list. Compilers warn with -Wreorder.
namespace section8 {

class Rectangle {
    int width_;   // 1st: initialized first
    int height_;  // 2nd: initialized second
    int area_;    // 3rd: initialized LAST, regardless of list order

public:
    // BUG: 'area_' is listed first, but it reads width_/height_,
    // which have NOT been initialized yet (they are still garbage).
    Rectangle(int w, int h)
        : area_(width_ * height_), // reads uninitialized members!
          width_(w),
          height_(h)
    {
        area_ = width_ * height_; // patch up in body to fix the bug
    }

    ~Rectangle() = default;

    // CORRECT version (no warning, no bug):
    // Rectangle(int w, int h) : width_(w), height_(h), area_(w * h) {}
};

inline void run() {
    Rectangle r(10, 5); // -Wreorder warning fires here
}

} // namespace section8
