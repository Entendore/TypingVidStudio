// ============================================================================
// LESSON 29 - Const Generics + Traits
// ============================================================================
// Type parameters abstract over TYPES; const parameters abstract over
// COMPILE-TIME VALUES. Traits bind them together: one impl block for
// every array length, guards like "N >= 1", and associated consts
// computed from const parameters.
//
// Run me:  rustc --edition 2021 29_const_generics_and_traits.rs && ./29_const_generics_and_traits
// ============================================================================

use std::fmt::Debug;

// 1. const generic parameter: N is a compile-time VALUE.
//    One function accepts arrays of every length - no hand-written copies.
fn inspect<T: Debug, const N: usize>(arr: &[T; N]) {
    println!("[; {:>2}] = {:?}", N, arr);
}

// 2. ONE impl covers [i64; 0], [i64; 1], ... [i64; whatever]:
trait Total {
    fn total(&self) -> i64;
}

impl<const N: usize> Total for [i64; N] {
    fn total(&self) -> i64 {
        self.iter().sum()
    }
}

// 3. MINIMUM SIZE: require N >= 1 using the "[(); N - 1]" trick.
//    For N = 0 the subtraction overflows in the type system, the
//    where-clause fails, and this impl simply doesn't exist for [i64; 0].
trait Head {
    fn head(&self) -> i64;
}

impl<const N: usize> Head for [i64; N] where [(); N - 1]: {
    fn head(&self) -> i64 {
        self[0]
    }
}

// 4. ASSOCIATED CONSTS (lesson 08) fed by const parameters:
trait Bounded {
    const CAPACITY: usize;
    fn used(&self) -> usize;

    // Default methods may use the const:
    fn remaining(&self) -> usize {
        Self::CAPACITY - self.used()
    }
}

struct RingBuffer<const N: usize> {
    buf: [u8; N],
    used: usize,
}

impl<const N: usize> RingBuffer<N> {
    fn new() -> Self {
        RingBuffer { buf: [0; N], used: 0 }
    }
}

impl<const N: usize> Bounded for RingBuffer<N> {
    const CAPACITY: usize = N; // the const parameter becomes the const

    fn used(&self) -> usize {
        self.used
    }
}

fn main() {
    inspect(&[1, 2]);
    inspect(&[1, 2, 3]);
    inspect(&['a', 'b', 'c', 'd']);

    println!("total of [3, 1, 4, 1, 5] = {}", [3, 1, 4, 1, 5].total());

    println!("head of [9, 8, 7] = {}", [9, 8, 7].head());
    //
    // let empty: [i64; 0] = [];
    // empty.head();
    // ^^^ ERROR if uncommented: "the trait bound `[i64; 0]: Head` is not
    //     satisfied" - the [(); N - 1] guard excluded length 0 on purpose.

    let mut rb = RingBuffer::<8>::new();
    rb.used = 3;
    println!(
        "ring buffer: {}/{} used, {} remaining",
        rb.used,
        RingBuffer::<8>::CAPACITY,
        rb.remaining()
    );

    // You already USE const generics daily: [T; N] itself, IntoIterator
    // for arrays, and N-dimensional vector crates (nalgebra, glam).
}
