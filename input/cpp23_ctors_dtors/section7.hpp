#pragma once
#include "common.hpp"

// =============================================================================
// SECTION 7 — INHERITING CONSTRUCTORS (C++11/17)
// =============================================================================
namespace section7 {

class Shape {
protected:
    std::string color_;
public:
    Shape() : color_("black") {}
    explicit Shape(std::string c) : color_(std::move(c)) {}
    virtual ~Shape() {}
};

class Circle : public Shape {
    // C++17: Inherited ctors will initialize derived members using their 
    // default member initializers.
    double radius_ = 1.0; 
public:
    using Shape::Shape; // INHERIT all Shape constructors

    ~Circle() override {}

    void describe() const { /* uses color_ and radius_ */ }
};

inline void run() {
    Circle c1;           // inherited default ctor. radius_ becomes 1.0.
    Circle c2("red");    // inherited Shape(string) ctor. radius_ becomes 1.0.
    c1.describe();
    c2.describe();
}

} // namespace section7
