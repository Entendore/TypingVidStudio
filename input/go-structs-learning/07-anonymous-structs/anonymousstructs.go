// ============================================================================
// EXAMPLE 07 — ANONYMOUS STRUCTS
// ============================================================================
//
// An anonymous struct is a struct TYPE written inline, with no name:
//
//     struct {
//         Host string
//         Port int
//     }
//
// Use it when a type is needed exactly ONCE and a named type would
// be ceremony: table-driven tests, one-off reports, quick configs.
//
// TYPE IDENTITY (the subtle part): two anonymous struct types with
// the SAME fields (names, types, order) are literally THE SAME type —
// values assign freely between them. A named type is always distinct,
// even with identical fields, and needs an explicit conversion.
package main

import "fmt"

func main() {
    // ------------------------------------------------------------------------
    // 1) DECLARE + INITIALIZE IN ONE EXPRESSION
    // ------------------------------------------------------------------------
    server := struct {
        Host string
        Port int
    }{
        Host: "localhost", // named fields, like any composite literal
        Port: 8080,
    }
    fmt.Printf("%s:%d\n", server.Host, server.Port) // localhost:8080

    // ------------------------------------------------------------------------
    // 2) TYPE IDENTITY — anonymous types with identical shape are ONE type
    // ------------------------------------------------------------------------
    s1 := struct{ X, Y int }{1, 2}
    var s2 struct{ X, Y int } = s1 // compiles: same unnamed type
    fmt.Println("s1 == s2:", s1 == s2) // true

    // A NAMED type with the same fields is a DIFFERENT type:
    type Point struct{ X, Y int }
    p := Point(s1) // conversion REQUIRED (legal: same underlying shape)
    fmt.Println("converted:", p)

    // ------------------------------------------------------------------------
    // 3) THE CLASSIC USE — TABLE-DRIVEN TESTS
    // ------------------------------------------------------------------------
    //
    // A slice of anonymous structs: no type to invent, no name to
    // bikeshed, lives and dies inside one function. This exact shape
    // is idiomatic in real Go test files (see example 14's tests).
    tests := []struct {
        name string
        in   int
        want int
    }{
        {"zero", 0, 0},
        {"positive", 3, 9},
        {"negative", -3, 9},
    }
    for _, tc := range tests {
        got := tc.in * tc.in
        status := "ok"
        if got != tc.want {
            status = "FAIL"
        }
        fmt.Printf("  %-9s square(%d)=%d [%s]\n", tc.name, tc.in, got, status)
    }

    // ------------------------------------------------------------------------
    // 4) QUICK REPORTS — ad-hoc aggregates with zero ceremony
    // ------------------------------------------------------------------------
    items := []struct {
        Name  string
        Price float64
    }{
        {"coffee", 3.50},
        {"tea", 2.75},
    }
    total := 0.0
    for _, it := range items {
        fmt.Printf("  %-7s $%.2f\n", it.Name, it.Price)
        total += it.Price
    }
    fmt.Printf("  total:  $%.2f\n", total)

    // ------------------------------------------------------------------------
    // RULE OF THUMB
    // ------------------------------------------------------------------------
    // If the shape appears in TWO places, or has METHODS, or is part
    // of a public API — promote it to a named type. Anonymous structs
    // are for locals only.
}
