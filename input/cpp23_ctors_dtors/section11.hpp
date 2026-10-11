#pragma once
#include "common.hpp"

// =============================================================================
// SECTION 11 — THE DON'Ts (Anti-Patterns)
// =============================================================================
namespace section11 {

// --- DON'T #1: Call virtual functions from constructors/destructors ---------
class Base {
public:
    Base() {
        // BUG: Calls Base::describe(), NOT Derived::describe().
        // During Base's ctor, the Derived part doesn't exist yet.
        describe(); 
    }
    virtual void describe() const {}
    virtual ~Base() {
        // Same issue: Derived part is already destroyed.
        describe(); 
    }
};

class Derived : public Base {
    std::string data_ = "derived-data";
public:
    void describe() const override { /* uses data_ */ }
};

// --- DON'T #2: Throw from a destructor --------------------------------------
class BadDtor {
public:
    ~BadDtor() noexcept(false) {
        // throw std::runtime_error("dtor failure"); 
        // If thrown during stack unwinding, std::terminate kills the program.
    }
};

// --- DON'T #3: Forget noexcept on move operations ---------------------------
class SlowMove {
    std::vector<int> data_;
public:
    explicit SlowMove(int n) : data_(n, 42) {}
    // Missing noexcept! std::vector will COPY, not MOVE, on reallocation.
    SlowMove(SlowMove&& o) : data_(std::move(o.data_)) {} 
};

// --- DON'T #4: Forget explicit on single-argument constructors -------------
class Money {
    double amount_;
public:
    Money(double a) : amount_(a) {}   // NOT explicit!
    // Allows accidental conversions: pay(50) compiles if function takes Money.
};

// --- DON'T #5: Forget to reset moved-from state -----------------------------
class UnsafeMove {
    int* data_;
public:
    explicit UnsafeMove(int n) : data_(new int[n]) {}
    ~UnsafeMove() { delete[] data_; }
    UnsafeMove(UnsafeMove&& o) noexcept : data_(o.data_) {
        // BUG: forgot to null out o.data_. 
        // Both destructors will delete the same pointer → DOUBLE FREE.
    }
};

inline void run() {
    // Anti-patterns compiled for review.
}

} // namespace section11
