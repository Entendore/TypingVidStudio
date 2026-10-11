#pragma once
#include "common.hpp"
#include "section1.hpp" // Needed for HeapBuffer

// =============================================================================
// SECTION 3 — VIRTUAL DESTRUCTORS & CONSTRUCTION ORDER
// =============================================================================
// Construction order:  Base → Members (declaration order) → Derived body
// Destruction order:   Derived body → Members (reverse) → Base  (exact reverse)
namespace section3 {

class Component {
    std::string name_;
public:
    explicit Component(std::string n) : name_(std::move(n)) {}
    ~Component() {} // Non-virtual is fine here, held by value, not polymorphically.
};

class Entity {
    Component physics_;   // Constructed 1st
    Component graphics_;  // Constructed 2nd
public:
    Entity() : physics_("Physics"), graphics_("Graphics") {}
    
    // MUST be virtual. If not, deleting a Player* via an Entity* would skip
    // ~Player(), leaking the Player's specific resources.
    virtual ~Entity() {} 
};

class Player : public Entity {
    section1::HeapBuffer inventory_; // Reusing our HeapBuffer from Section 1
public:
    // Base class constructor runs first, then members, then this body.
    Player() : Entity(), inventory_(16) {}
    ~Player() override {} // Overrides base destructor. Runs before ~Entity().
};

inline void run() {
    // Polymorphic deletion: safely calls ~Player(), then ~Entity().
    Entity* e = new Player();
    delete e; 
}

} // namespace section3
