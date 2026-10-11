// SOLUTION 3 - dyn compatibility via &dyn parameter (lesson 16)
// FIX: a generic METHOD is the dyn-blocker (one vtable slot can't cover all
// T). Replace the type parameter with a trait OBJECT parameter:
//     fn check<T: Display>(&self, value: T)
//  -> fn check(&self, value: &dyn Display)
// Trade-off: you lose monomorphized speed, you gain object safety.

use std::fmt::Display;

trait Validator {
    fn check(&self, value: &dyn Display) -> bool;
}

struct NonEmpty;

impl Validator for NonEmpty {
    fn check(&self, value: &dyn Display) -> bool {
        !value.to_string().is_empty()
    }
}

fn main() {
    let validators: Vec<Box<dyn Validator>> = vec![Box::new(NonEmpty)];
    for v in &validators {
        println!("check(\"hi\") = {}", v.check("hi"));
        println!("check(\"\")   = {}", v.check(""));
    }
}
