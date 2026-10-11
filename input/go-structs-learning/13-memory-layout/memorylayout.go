// ============================================================================
// EXAMPLE 13 — MEMORY LAYOUT: ALIGNMENT, PADDING, STRUCT SIZE
// ============================================================================
//
// The CPU reads memory in aligned chunks (an int64 wants to start at
// an address divisible by 8). To guarantee alignment, the compiler
// inserts invisible PADDING bytes between fields. Therefore:
//
//     struct size >= sum of field sizes
//
// and FIELD ORDER determines how much is wasted.
//
// (Sizes/offsets below are for 64-bit platforms.)
//
// PoorlyOrdered — bool, int64, bool:
//
//     offset 0:  a bool    (1 byte)
//     offset 1:  ▒▒▒▒▒▒▒   (7 bytes PADDING so b can align to 8)
//     offset 8:  b int64   (8 bytes)
//     offset 16: c bool    (1 byte)
//     offset 17: ▒▒▒▒▒▒▒   (7 bytes TRAILING padding — so that in
//                           a []PoorlyOrdered the NEXT element's
//                           int64 is also aligned)
//                            => 24 bytes for 10 bytes of data
//
// WellOrdered — bool, bool, int64:
//
//     offset 0:  a bool    (1 byte)
//     offset 1:  c bool    (1 byte)
//     offset 2:  ▒▒▒▒▒▒    (6 bytes padding)
//     offset 8:  b int64   (8 bytes)   => 16 bytes — 33% smaller
//
package main

import (
    "fmt"
    "unsafe"
)

// 24 bytes: 1 + pad(7) + 8 + 1 + pad(7)
type PoorlyOrdered struct {
    a bool
    b int64
    c bool
}

// 16 bytes: 1 + 1 + pad(6) + 8 — SAME data, 8 bytes smaller
type WellOrdered struct {
    a, c bool
    b    int64
}

func main() {
    // ------------------------------------------------------------------------
    // unsafe.Sizeof — total bytes INCLUDING padding
    // ------------------------------------------------------------------------
    // (unsafe here means "no guarantees across versions/platforms",
    // not "dangerous" — Sizeof/Alignof/Offsetof are compile-time
    // constants and perfectly fine for diagnostics.)
    fmt.Println("poor:", unsafe.Sizeof(PoorlyOrdered{}), "bytes") // 24
    fmt.Println("good:", unsafe.Sizeof(WellOrdered{}), "bytes")   // 16

    // ------------------------------------------------------------------------
    // unsafe.Alignof — a type's alignment requirement in bytes
    // ------------------------------------------------------------------------
    fmt.Println("align int64:", unsafe.Alignof(int64(0))) // 8
    fmt.Println("align bool: ", unsafe.Alignof(false))    // 1

    // ------------------------------------------------------------------------
    // unsafe.Offsetof — WHERE each field sits: SEE the padding
    // ------------------------------------------------------------------------
    var p PoorlyOrdered
    fmt.Println("poor offsets: a=%d b=%d c=%d ->" ,
        unsafe.Offsetof(p.a), unsafe.Offsetof(p.b), unsafe.Offsetof(p.c))
    // a=0, b=8 (7 bytes of padding before it), c=16

    var w WellOrdered
    fmt.Println("good offsets: a=%d c=%d b=%d ->",
        unsafe.Offsetof(w.a), unsafe.Offsetof(w.c), unsafe.Offsetof(w.b))
    // a=0, c=1 (packed together!), b=8

    // ------------------------------------------------------------------------
    // WHY IT MATTERS
    // ------------------------------------------------------------------------
    //
    //   * slices of structs multiply the waste:
    //         1,000,000 PoorlyOrdered = 24 MB
    //         1,000,000 WellOrdered   = 16 MB   (8 MB of pure padding)
    //
    //   * cache lines are 64 bytes: tighter structs -> more structs
    //     per cache line -> measurably faster hot loops
    //
    //   * the 'fieldalignment' vet check finds bad orderings
    //     automatically:  go vet -fieldalignment ./...
    //
    // RULE: order fields LARGEST to SMALLEST and you'll never be far
    // from optimal. Don't hand-pad or rely on exact layout — it is
    // explicitly not guaranteed by the spec and may change.
}
