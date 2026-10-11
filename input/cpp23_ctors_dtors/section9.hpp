#pragma once
#include "common.hpp"

// =============================================================================
// SECTION 9 — EXCEPTION SAFETY IN CONSTRUCTORS
// =============================================================================
// If a constructor throws, any members that were ALREADY constructed are
// automatically destroyed in reverse order. The object itself is NOT created.
namespace section9 {

class TrackedResource {
    int id_;
public:
    explicit TrackedResource(int id) : id_(id) {}
    ~TrackedResource() {} // cleans up
};

class RiskyConstructor {
    TrackedResource r1_;
    TrackedResource r2_;
    TrackedResource r3_;

public:
    RiskyConstructor()
        : r1_(1), r2_(2), r3_(3) // All three are fully constructed.
    {
        // Exception thrown in body.
        // r3_, r2_, r1_ destructors WILL run (in reverse order).
        // ~RiskyConstructor will NOT run (object never fully existed).
        throw std::runtime_error("simulated failure in constructor body");
    }
    ~RiskyConstructor() {} 
};

inline void run() {
    try {
        RiskyConstructor rc;
    } catch (const std::exception& e) {
        // Caught. All sub-members were safely cleaned up by the compiler.
    }
}

} // namespace section9
