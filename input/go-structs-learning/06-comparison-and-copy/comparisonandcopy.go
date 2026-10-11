// ============================================================================
// EXAMPLE 06 — COPY SEMANTICS, EQUALITY, STRUCTS AS MAP KEYS
// ============================================================================
//
// Structs are VALUES. Assignment, arguments, and returns COPY the
// whole struct — every field, byte for byte. There is no implicit
// reference semantics anywhere in Go.
package main

import (
    "fmt"
    "reflect"
)

type Coords struct {
    X, Y int
}

// Team contains a SLICE — and that changes everything below.
type Team struct {
    Name    string
    Members []string
}

func main() {
    // ------------------------------------------------------------------------
    // 1) ASSIGNMENT = FULL COPY
    // ------------------------------------------------------------------------
    //
    //     a: ┌───────┐        b := a      a: ┌───────┐
    //        │ X: 1  │       ─────────>     │ X: 1  │
    //        │ Y: 2  │                      │ Y: 2  │
    //        └───────┘                      └───────┘
    //                                        b: ┌───────┐
    //                                           │ X: 1  │  (a new block,
    //                                           │ Y: 2  │   fully separate)
    //                                           └───────┘
    //
    a := Coords{X: 1, Y: 2}
    b := a // entire struct copied
    b.X = 99
    fmt.Println("a:", a, "| b:", b) // a unchanged: {1 2} {99 2}

    // Equality follows from copy semantics — compare field by field:
    fmt.Println("a == Coords{1,2}:", a == Coords{1, 2}) // true

    // ------------------------------------------------------------------------
    // 2) WHEN == IS ILLEGAL
    // ------------------------------------------------------------------------
    //
    // A struct is comparable only if ALL its fields are. Slices, maps,
    // and functions are NOT comparable (== on them is a compile error):
    //
    //     t1 == t2        // COMPILE ERROR — Team has a slice field
    //
    // The error message says "invalid operation: Team == Team
    // (struct containing []string cannot be compared)".
    //
    // For deep comparison use reflect.DeepEqual (runtime, slower,
    // and treats nil slices != empty slices — be careful):
    t1 := Team{Name: "red", Members: []string{"ada"}}
    t2 := Team{Name: "red", Members: []string{"ada"}}
    fmt.Println("DeepEqual:", reflect.DeepEqual(t1, t2)) // true

    // ------------------------------------------------------------------------
    // 3) COMPARABLE STRUCTS MAKE EXCELLENT MAP KEYS
    // ------------------------------------------------------------------------
    //
    // Map keys must be comparable — so structs without slices/maps
    // work perfectly as composite keys (Coords in a grid, date+user,
    // etc.). This is impossible in many languages without wrapping.
    m := map[Coords]string{
        {X: 0, Y: 0}: "origin",
        {X: 1, Y: 1}: "northeast",
    }
    fmt.Println("map lookup:", m[Coords{X: 0, Y: 0}]) // origin

    // ------------------------------------------------------------------------
    // 4) COPY vs SHARE — you choose, explicitly
    // ------------------------------------------------------------------------
    //
    // Passing t by value copies it (mutations invisible to caller).
    // Passing &t shares one copy (mutations visible). Example 17
    // covers the trap: copies share slice/map BACKING data.
    rename := func(t *Team, name string) { t.Name = name }
    rename(&t1, "blue")
    fmt.Println("renamed:", t1.Name) // blue — caller sees it
}
