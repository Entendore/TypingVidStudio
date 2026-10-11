// ============================================================================
// WORKBOOK EX 5 - Escape the Orphan Rule with a Newtype
// ============================================================================
// EXPECTED ERROR:  E0117 "only traits defined in the current crate can be
//                  implemented for arbitrary types" (lesson 09)
//
// TASK (two steps):
//   1. Read the E0117 error from the forbidden impl below. DELETE it.
//   2. Finish the newtype `Scores` (lesson 24): store a Vec<i32> and make
//      Display print like  [10, 20, 30]
//
// Then compare:  solutions/ex05_orphan_rule_rescue.rs
// Run:  rustc --edition 2021 ex05_orphan_rule_rescue.rs && ./ex05_orphan_rule_rescue
// ============================================================================

use std::fmt;

// STEP 1 - forbidden: we own neither `Display` nor `Vec`. Delete me!
impl fmt::Display for Vec<i32> {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "???")
    }
}

// STEP 2 - the newtype escape hatch:
struct Scores(/* TODO: add the field */);

impl fmt::Display for Scores {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        // TODO: print like [10, 20, 30]
        // Hint: map each number to a String, collect, join(", ")
        todo!()
    }
}

fn main() {
    let s = Scores(vec![10, 20, 30]);
    println!("{}", s); // want: [10, 20, 30]
}
