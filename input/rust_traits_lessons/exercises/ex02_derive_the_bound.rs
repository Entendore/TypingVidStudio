// ============================================================================
// WORKBOOK EX 2 - Satisfy a Trait Bound
// ============================================================================
// EXPECTED ERROR:  E0277 "`Sensor` doesn't implement `Debug`"
//
// TASK: make the code compile with the SMALLEST possible change.
// (Two valid fixes exist - can you find both? The canonical one is 1 line.)
//
// Then compare:  solutions/ex02_derive_the_bound.rs
// Run:  rustc --edition 2021 ex02_derive_the_bound.rs && ./ex02_derive_the_bound
// ============================================================================

use std::fmt::Debug;

struct Sensor {
    id: u32,
    reading: f64,
}

fn print_all<T: Debug>(items: &[T]) {
    for it in items {
        println!("{:?}", it);
    }
}

fn main() {
    let sensors = vec![
        Sensor { id: 1, reading: 21.5 },
        Sensor { id: 2, reading: 19.0 },
    ];
    print_all(&sensors); // <- E0277 here
}
