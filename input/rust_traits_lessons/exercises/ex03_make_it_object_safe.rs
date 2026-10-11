// ============================================================================
// WORKBOOK EX 3 - Make the Trait dyn-Compatible (Object Safety)
// ============================================================================
// EXPECTED ERROR:  E0038 "the trait `Validator` is not dyn compatible ...
//                  method `check` is generic"
//
// TASK: change the Validator trait (and its impl / call sites) so that
//       Box<dyn Validator> works. Keep the SAME behavior.
//       Hint: lesson 16's Fix A - take `&dyn Display` instead of `T`.
//
// Then compare:  solutions/ex03_make_it_object_safe.rs
// Run:  rustc --edition 2021 ex03_make_it_object_safe.rs && ./ex03_make_it_object_safe
// ============================================================================

use std::fmt::Display;

trait Validator {
    fn check<T: Display>(&self, value: T) -> bool; // <- generic method: no dyn!
}

struct NonEmpty;

impl Validator for NonEmpty {
    fn check<T: Display>(&self, value: T) -> bool {
        !value.to_string().is_empty()
    }
}

fn main() {
    let validators: Vec<Box<dyn Validator>> = vec![Box::new(NonEmpty)]; // <- E0038
    for v in &validators {
        println!("check(\"hi\") = {}", v.check("hi"));
        println!("check(\"\")   = {}", v.check(""));
    }
}
