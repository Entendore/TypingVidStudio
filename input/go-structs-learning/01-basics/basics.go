// ============================================================================
// EXAMPLE 01 — STRUCT BASICS
// ============================================================================
//
// A struct is a fixed-size collection of NAMED FIELDS stored together in
// one contiguous block of memory. It is Go's ONLY way to group data —
// there are no classes, no inheritance, no constructors. Everything else
// (methods, interfaces, embedding) is layered on top of structs.
//
// A Rectangle occupies ONE contiguous block (float64 = 8 bytes each):
//
//        ┌──────────────┬──────────────┐
//        │  Width (8B)  │ Height (8B)  │
//        └──────────────┴──────────────┘
//        addr+0         addr+8
//
// Structs are VALUE types: assigning one copies every field (example 06).
package main

import "fmt"

// ----------------------------------------------------------------------------
// DECLARING STRUCT TYPES
// ----------------------------------------------------------------------------
//
//     type <Name> struct {
//         <Field> <Type>
//     }
//
// FIELD VISIBILITY — a capital letter IS Go's access modifier:
//
//     Width   -> exported : visible outside this package
//     width   -> unexported : private to package "main"
//
// There is no public/private/protected keyword. The case of the first
// letter of the name decides everything.
type Rectangle struct {
    Width  float64 // exported — other packages may read AND write
    Height float64 // exported
}

// A struct may mix any field types — scalars, strings, slices, other
// structs, pointers, even interfaces (examples 15 and 18).
type Person struct {
    Name string
    Age  int
}

func main() {
    // ------------------------------------------------------------------------
    // 1) DECLARATION WITHOUT INITIALIZATION — every field gets its ZERO VALUE
    // ------------------------------------------------------------------------
    //
    // Go never leaves memory uninitialized. Zero values per type:
    //
    //     numbers          -> 0
    //     strings          -> ""      (empty string, NOT nil)
    //     bools            -> false
    //     pointers/slices  -> nil
    //     maps             -> nil     (reads OK, writes PANIC — see ex. 17)
    //     structs          -> recursively, zero value of every field
    //
    var r Rectangle // {Width:0, Height:0}
    fmt.Println("1) zero value:", r) // output: {0 0}

    // Fields behave exactly like ordinary variables — read and write
    // them with dot notation:
    r.Width = 10
    r.Height = 5

    // ------------------------------------------------------------------------
    // 2) COMPOSITE LITERAL — the idiomatic way to build a struct
    // ------------------------------------------------------------------------
    //
    // Field:value pairs. Omitted fields silently get zero values.
    p := Person{Name: "Ada", Age: 36}
    fmt.Printf("2) %s is %d years old\n", p.Name, p.Age)

    // ------------------------------------------------------------------------
    // 3) PRINTING STRUCTS — three fmt verbs worth memorizing
    // ------------------------------------------------------------------------
    //
    //     %v   {10 5}                 bare values
    //     %+v  {Width:10 Height:5}    values WITH field names
    //     %#v  main.Rectangle{...}    Go-syntax — valid source code
    //
    fmt.Printf("3) %%v : %v\n", r)
    fmt.Printf("   %%+v: %+v\n", r)
    fmt.Printf("   %%#v: %#v\n", p)

    // ------------------------------------------------------------------------
    // 4) FIELDS IN EXPRESSIONS — use them like any other value
    // ------------------------------------------------------------------------
    fmt.Println("4) area:", r.Width*r.Height) // 50

    // ------------------------------------------------------------------------
    // 5) STRUCT EQUALITY — == compares field by field, in order
    // ------------------------------------------------------------------------
    //
    // Works ONLY if every field type is comparable (numbers, strings,
    // bools, pointers, arrays, comparable structs...). A single slice
    // or map field makes == ILLEGAL — see example 06.
    a := Rectangle{Width: 1, Height: 2}
    b := Rectangle{Width: 1, Height: 2}
    fmt.Println("5) a == b:", a == b) // true — all fields equal

    // The zero struct is a valid comparison target:
    var c Rectangle
    fmt.Println("   c == zero:", c == Rectangle{}) // true
}
