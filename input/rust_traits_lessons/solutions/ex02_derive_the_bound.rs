// SOLUTION 2 - satisfy the Debug bound (lessons 03, 06)
// FIX A (canonical, 1 line): #[derive(Debug)] - Debug is derivable because
//      every field is Debug (lesson 09: deriveable marker/workhorse traits).
// FIX B (shown below, commented): hand-write fmt::Debug like in lesson 06.
// The error E0277 literally told us which bound was missing - read it first!

use std::fmt::Debug;

#[derive(Debug)] // <- the fix
struct Sensor {
    id: u32,
    reading: f64,
}

// FIX B alternative:
// use std::fmt;
// impl fmt::Debug for Sensor {
//     fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
//         write!(f, "Sensor #{} @ {:.1}", self.id, self.reading)
//     }
// }

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
    print_all(&sensors);
}
