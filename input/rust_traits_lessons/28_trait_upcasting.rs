// ============================================================================
// LESSON 28 - Trait Upcasting: dyn Subtrait -> dyn Supertrait
// ============================================================================
// Requires Rust 1.86+ for the direct coercions.
// For centuries (2012-2025!) Rust refused `&dyn Dog -> &dyn Animal` even
// though every Dog IS an Animal. Now it just works - for references,
// Box, Rc, and Arc alike.
//
// Run me:  rustc --edition 2021 28_trait_upcasting.rs && ./28_trait_upcasting
// ============================================================================

use std::rc::Rc;

trait Animal {
    fn name(&self) -> &str;
}

// Supertrait bound (lesson 09): every Dog IS an Animal.
trait Dog: Animal {
    fn breed(&self) -> &'static str;
}

struct Labrador;
struct Poodle;

impl Animal for Labrador {
    fn name(&self) -> &str {
        "Biscuit"
    }
}
impl Dog for Labrador {
    fn breed(&self) -> &'static str {
        "Labrador"
    }
}

impl Animal for Poodle {
    fn name(&self) -> &str {
        "Coco"
    }
}
impl Dog for Poodle {
    fn breed(&self) -> &'static str {
        "Poodle"
    }
}

// A function that only needs the SUPERTRAIT's abilities:
fn describe(animal: &dyn Animal) -> String {
    format!("{} (some kind of animal)", animal.name())
}

fn main() {
    // --- references: &dyn Dog -> &dyn Animal (the 1.86 feature) ---
    let lab = Labrador;
    let dog: &dyn Dog = &lab;
    let animal: &dyn Animal = dog; // <- the upcast. Pre-1.86: compile error!
    println!("ref:    {}", animal.name());

    // It also applies at ordinary call sites (coercion sites):
    println!("call:   {}", describe(dog));

    // --- owning pointers: Box upcasts by MOVING ownership up ---
    let dog: Box<dyn Dog> = Box::new(Poodle);
    let animal: Box<dyn Animal> = dog;
    println!("box:    {}", animal.name());

    // --- Rc / Arc upcast too (clone first if you need both views) ---
    let dog: Rc<dyn Dog> = Rc::new(Labrador);
    let animal: Rc<dyn Animal> = Rc::clone(&dog);
    println!("rc:     {} (strong={})", animal.name(), Rc::strong_count(&dog));

    // --- the mirror direction is still forbidden ---
    // let dog: Box<dyn Dog> = animal;
    // ^^^ ERROR: can't downcast - `animal` might be ANY animal, not a Dog.
    // True runtime-checked downcasting needs std::any::Any + downcast_ref.

    // --- BEFORE 1.86 (and still a useful pattern): hand-rolled upcast ---
    //
    //     trait Dog: Animal {
    //         fn as_animal(&self) -> &dyn Animal { self }  // default body
    //     }
    //     let animal: &dyn Animal = dog.as_animal();
    //
    // WHY IT MATTERS: supertrait-bounded dyn objects (see capstone 33, where
    // &dyn Step becomes &dyn Display), plugin registries, and erasing
    // capabilities you no longer need.
}
