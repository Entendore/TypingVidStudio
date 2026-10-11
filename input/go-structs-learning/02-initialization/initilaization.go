// ============================================================================
// EXAMPLE 02 — EVERY WAY TO INITIALIZE A STRUCT (+ POINTERS)
// ============================================================================
//
// Six initialization forms, when to use each, and how pointers to
// structs work (no "->" operator — Go auto-dereferences).
package main

import "fmt"

type Point struct {
    X, Y int // two fields on one line is legal Go
}

func main() {
    // ------------------------------------------------------------------------
    // 1) NAMED-FIELD LITERAL — THE DEFAULT CHOICE
    // ------------------------------------------------------------------------
    //
    // Point{X: ..., Y: ...}
    //   * field names make the call self-documenting
    //   * order does not matter
    //   * omitted fields get zero values
    //   * adding a field later breaks NOTHING
    //
    p1 := Point{X: 1, Y: 2}
    fmt.Println("1) named:     ", p1) // {1 2}

    // ------------------------------------------------------------------------
    // 2) POSITIONAL LITERAL — LEGAL BUT DISCOURAGED
    // ------------------------------------------------------------------------
    //
    // Point{3, 4}
    //   * values MUST be in declaration order
    //   * ALL fields must be listed
    //   * reordering or adding a field breaks every call site
    //
    // Use it only for tiny, obviously-ordered structs (like Point here).
    p2 := Point{3, 4}
    fmt.Println("2) positional:", p2) // {3 4}

    // ------------------------------------------------------------------------
    // 3) PARTIAL LITERAL — missing fields become zero values
    // ------------------------------------------------------------------------
    p3 := Point{X: 9}
    fmt.Println("3) partial:   ", p3) // {9 0} — Y silently 0

    // ------------------------------------------------------------------------
    // 4) new(T) — allocate a zero-valued T, return a POINTER to it
    // ------------------------------------------------------------------------
    //
    // new(Point) is exactly equivalent to &Point{}.
    // Note the result type is *Point — new takes the TYPE, not a value.
    p4 := new(Point) // *Point, pointing at {0, 0}
    p4.X, p4.Y = 5, 6
    fmt.Println("4) new():     ", *p4, "| type:", fmt.Sprintf("%T", p4))

    // ------------------------------------------------------------------------
    // 5) ADDRESS-OF LITERAL — &T{...} — the everyday pointer pattern
    // ------------------------------------------------------------------------
    //
    // Combines "make one" and "take its address" in a single expression.
    // This is what you'll see in real code 90% of the time, especially
    // as the argument to functions that take *T.
    p5 := &Point{X: 7, Y: 8}
    fmt.Println("5) &literal:  ", *p5, "| type:", fmt.Sprintf("%T", p5))

    // ------------------------------------------------------------------------
    // 6) &T{} — pointer to a zero struct: "I'll fill it in later"
    // ------------------------------------------------------------------------
    p6 := &Point{}
    p6.X = 42
    fmt.Println("6) &Point{}:  ", *p6)

    // ------------------------------------------------------------------------
    // POINTER ACCESS — Go AUTO-DEREFERENCES, there is no "->" operator
    // ------------------------------------------------------------------------
    //
    // C/C++ require (*p).field or p->field. Go accepts the explicit
    // form but the shorthand p.field is always what you write:
    //
    //     p5.X     is shorthand for     (*p5).X
    //
    p5.X = 100     // shorthand — what everyone writes
    (*p5).Y = 200  // explicit — identical semantics
    fmt.Println("auto-deref:   ", *p5) // {100 200}

    // ------------------------------------------------------------------------
    // WHICH FORM WHEN? — the RULE
    // ------------------------------------------------------------------------
    //
    //   * need the value?                 -> Point{...}
    //   * passing to something that
    //     takes *T (mutation, big struct) -> &Point{...}
    //   * declaration only, assign later  -> p := &Point{}
    //   * new(T)                          -> rare; &T{} reads better
}
