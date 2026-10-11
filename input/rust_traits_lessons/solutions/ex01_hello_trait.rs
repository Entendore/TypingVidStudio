// SOLUTION 1 - the missing impl block (lessons 01, 02)
// FIX: any type used via a trait's methods must implement that trait.
// The compiler's E0599 note listed the missing bound `Pirate: Greeter`
// and even offered: "this can be fixed by implementing the trait".

trait Greeter {
    fn greeting(&self) -> String;

    fn announce(&self) -> String {
        format!("ATTENTION: {}!", self.greeting())
    }
}

struct Pirate {
    name: String,
}

impl Greeter for Pirate {
    fn greeting(&self) -> String {
        format!("Ahoy, {}!", self.name)
    }
    // announce() came free from the default implementation.
}

fn main() {
    let p = Pirate { name: "Redbeard".into() };
    println!("{}", p.greeting());
    println!("{}", p.announce());
}
