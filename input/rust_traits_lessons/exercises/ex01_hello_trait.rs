// ============================================================================
// WORKBOOK EX 1 - Write Your First impl
// ============================================================================
// EXPECTED ERROR:  E0599 "no method named `greeting` found for struct
//                  `Pirate` ... trait bounds were not satisfied: Pirate: Greeter"
//
// TASK: implement the Greeter trait for Pirate so that
//         greeting() returns  "Ahoy, Redbeard!" (using the name field)
//       Don't touch announce() - the default method (lesson 02) will
//       start working the moment your impl exists.
//
// Then compare:  solutions/ex01_hello_trait.rs
// Run:  rustc --edition 2021 ex01_hello_trait.rs && ./ex01_hello_trait
// ============================================================================

trait Greeter {
    fn greeting(&self) -> String;

    // FREE once you implement greeting(): (lesson 02)
    fn announce(&self) -> String {
        format!("ATTENTION: {}!", self.greeting())
    }
}

struct Pirate {
    name: String,
}

// TODO: write the impl block for Greeter for Pirate here.
// Hint: format!("Ahoy, {}!", self.name)

fn main() {
    let p = Pirate { name: "Redbeard".into() };
    println!("{}", p.greeting());
    println!("{}", p.announce());
}
