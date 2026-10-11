// ============================================================================
// WORKBOOK EX 4 - Implement Iterator (this one COMPILES but PANICS)
// ============================================================================
// EXPECTED RUNTIME BEHAVIOR: "not yet implemented" panic - todo!() runs.
//
// TASK: implement `next` so the for-loop prints:  3 2 1
//       - yield remaining, remaining-1, ... 1
//       - after reaching 0, return None FOREVER (lesson 11's contract)
//
// Then compare:  solutions/ex04_write_an_iterator.rs
// Run:  rustc --edition 2021 ex04_write_an_iterator.rs && ./ex04_write_an_iterator
// ============================================================================

struct Countdown {
    remaining: u32,
}

impl Iterator for Countdown {
    type Item = u32; // already correct - the work is in `next`

    fn next(&mut self) -> Option<u32> {
        // TODO: replace todo!() with real logic.
        todo!()
    }
}

fn main() {
    for n in Countdown { remaining: 3 } {
        print!("{} ", n);
    }
    println!();
}
