#pragma once
#include "common.hpp"

// =============================================================================
// SECTION 6 — DELEGATING CONSTRUCTORS (C++11)
// =============================================================================
// A constructor can call another constructor of the SAME class via the
// initializer list. The target constructor body executes BEFORE the delegating body.
namespace section6 {

class Config {
    std::string name_;
    int         timeout_;
    bool        verbose_;

public:
    // "Master" constructor — does all the real work
    Config(std::string name, int timeout, bool verbose)
        : name_(std::move(name)), timeout_(timeout), verbose_(verbose) {}

    // Delegating: calls the master. Master's body runs, then this body runs.
    Config() : Config("default", 3000, false) {}

    // Delegating: calls the master with one override
    explicit Config(std::string name) : Config(std::move(name), 5000, true) {}

    ~Config() {}
};

inline void run() {
    Config c1;                      // delegates to master
    Config c2("prod");             // delegates to master
    Config c3("dev", 1000, false); // calls master directly
}

} // namespace section6
