// SOLUTION 5 - newtype beats the orphan rule (lessons 09, 24)
// FIX: E0117 exists so two crates can't both claim `impl Display for Vec`.
// The escape hatch: a one-field tuple struct makes Vec<i32> into a type WE
// own (`Scores`), and a local type unlocks foreign trait impls. Zero
// runtime cost - same memory layout as the Vec itself.

use std::fmt;

struct Scores(Vec<i32>);

impl fmt::Display for Scores {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let parts: Vec<String> = self.0.iter().map(|n| n.to_string()).collect();
        write!(f, "[{}]", parts.join(", "))
    }
}

fn main() {
    let s = Scores(vec![10, 20, 30]);
    println!("{}", s); // [10, 20, 30]

    // Bonus: the wrapper can still reach the Vec cheaply via pattern match:
    let Scores(inner) = &s;
    println!("inner len = {}", inner.len());
}
