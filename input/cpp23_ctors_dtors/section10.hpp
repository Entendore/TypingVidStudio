#pragma once
#include "common.hpp"

// =============================================================================
// SECTION 10 — C++20 explicit(bool) — CONDITIONAL EXPLICIT
// =============================================================================
// C++20 lets a constructor be explicit ONLY when a compile-time condition
// is true. Standardized in C++20, widely usable in C++23 builds.
namespace section10 {

template<typename T>
class Wrapper {
    T value_;
public:
    // explicit(true)  when sizeof(T) > 4  → must write Wrapper<T>{x}
    // explicit(false) when sizeof(T) <= 4 → can write Wrapper<T> w = x
    explicit(sizeof(T) > 4) Wrapper(T v) : value_(v) {}

    T get() const { return value_; }
    ~Wrapper() = default;
};

inline void run() {
    Wrapper<int> w1 = 42;         // OK: sizeof(int) == 4, implicit allowed
    Wrapper<double> w3{3.14};      // OK: direct init required because sizeof(double) == 8
    // Wrapper<double> w2 = 3.14; // COMPILE ERROR: explicit(sizeof>4)
}

} // namespace section10
