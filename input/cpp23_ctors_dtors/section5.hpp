#pragma once
#include "common.hpp"

// =============================================================================
// SECTION 5 — C++23 `if consteval` IN A CONSTRUCTOR
// =============================================================================
namespace section5 {

struct BoundedValue {
    int value;

    consteval static int check(int v) {
        if (v < 0 || v > 100)
            throw std::out_of_range("BoundedValue out of range [0,100]");
        return v;
    }

    constexpr BoundedValue(int v) : value(v) {
        if consteval {
            // Compile-time path: validate immediately (constexpr context).
            // If check() fails, it's a hard compile error.
            value = check(v);
        } else {
            // Run-time path: throw a normal exception.
            if (v < 0 || v > 100)
                throw std::out_of_range("BoundedValue out of [0,100]");
        }
    }

    constexpr ~BoundedValue() = default; // constexpr dtor (C++20)
};

inline void run() {
    constexpr BoundedValue compile_time{50};   // OK, checked at compile time
    BoundedValue runtime_val{50};              // OK, checked at runtime
    
    try {
        BoundedValue bad_runtime{150};         // Throws at runtime
    } catch (...) {}
    
    // constexpr BoundedValue bad_compile{200}; // COMPILE ERROR!
}

} // namespace section5
