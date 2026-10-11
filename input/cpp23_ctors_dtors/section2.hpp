#pragma once
#include "common.hpp"

// =============================================================================
// SECTION 2 — = default / = delete  (Modern Idioms)
// =============================================================================
namespace section2 {

class UniqueHandle {
    int fd_;
public:
    explicit UniqueHandle(int fd) : fd_(fd) {}
    ~UniqueHandle() { /* close(fd_); */ }

    // FORBID copying — a file descriptor cannot be shared by value
    UniqueHandle(const UniqueHandle&)            = delete;
    UniqueHandle& operator=(const UniqueHandle&) = delete;

    // ALLOW moving — transfer ownership. We use std::exchange to safely steal
    // the value and leave the source in a valid "empty" state (-1).
    UniqueHandle(UniqueHandle&& o) noexcept : fd_(std::exchange(o.fd_, -1)) {}
    
    UniqueHandle& operator=(UniqueHandle&& o) noexcept {
        if (this != &o) {
            fd_ = std::exchange(o.fd_, -1);
        }
        return *this;
    }
};

inline void run() {
    UniqueHandle h1(42);
    UniqueHandle h2 = std::move(h1); // h1.fd_ is now -1. h2 owns 42.
    // UniqueHandle h3 = h2;         // COMPILE ERROR: copy is deleted
}

} // namespace section2
