// ============================================================================
// EXAMPLE 03 — METHODS: VALUE vs POINTER RECEIVERS
// ============================================================================
//
// A method is a function with a special first parameter — the RECEIVER —
// declared before the name. These two are semantically the same thing:
//
//     func (c Counter) Value() int { return c.count }   // method
//     func Value(c Counter) int    { return c.count }   // plain function
//
// The receiver is passed like any other parameter:
//
//   VALUE receiver    -> receives a COPY of the struct
//   POINTER receiver  -> receives a pointer; mutations are visible to caller
//
// Choosing wrong is the most common beginner bug, so learn the RULE at
// the bottom of this file.
package main

import "fmt"

type Counter struct {
    count int // unexported — only methods can touch it
}

// ----------------------------------------------------------------------------
// VALUE RECEIVER — c is a FULL COPY of the caller's struct
// ----------------------------------------------------------------------------
//
// Incrementing c.count changes the local copy only. The caller's
// Counter is untouched, so this method is nearly useless as written —
// we return the modified copy to make it meaningful.
func (c Counter) IncCopy() Counter {
    c.count++
    return c
}

// ----------------------------------------------------------------------------
// POINTER RECEIVER — c is a *Counter; we mutate through it
// ----------------------------------------------------------------------------
//
// c.count++ is shorthand for (*c).count++ — same auto-dereference
// as struct field access (example 02).
func (c *Counter) Inc() {
    c.count++
}

// Read-only accessor — a value receiver is fine for small structs.
func (c Counter) Value() int {
    return c.count
}

func main() {
    c := Counter{}

    // -------------------------------------------------------------------
    // AUTO-ADDRESSABILITY: calling a POINTER method on a VALUE
    // -------------------------------------------------------------------
    //
    // c is a value, but Inc() needs a *Counter. If c is ADDRESSABLE
    // (a variable — not a function result or map entry), the compiler
    // silently rewrites:
    //
    //     c.Inc()    ->    (&c).Inc()
    //
    c.Inc() // really (&c).Inc()
    c.Inc()
    c.Inc()
    fmt.Println("after Inc x3:", c.Value()) // 3

    // -------------------------------------------------------------------
    // VALUE receiver works on a copy — original is untouched
    // -------------------------------------------------------------------
    c2 := c.IncCopy()
    fmt.Println("copy vs original:", c2.Value(), c.Value()) // 4 3

    // -------------------------------------------------------------------
    // METHOD EXPRESSIONS — proof that receivers are just parameters
    // -------------------------------------------------------------------
    //
    // (*Counter).Inc is a plain function of type func(*Counter).
    // You'll rarely use this, but it demystifies what a method IS.
    inc := (*Counter).Inc
    inc(&c) // pass the receiver explicitly
    fmt.Println("via method expr:", c.Value()) // 4

    // -------------------------------------------------------------------
    // THE RULE (memorize this)
    // -------------------------------------------------------------------
    //
    // Use a POINTER receiver when:
    //   1. the method must MUTATE the receiver
    //   2. the struct is LARGE (copying costs time and memory)
    //   3. ANY other method of the type uses a pointer receiver —
    //      consistency keeps the method set predictable (see ex. 09)
    //
    // Use a VALUE receiver when:
    //   1. the method only READS the struct
    //   2. the struct is small (a few words)
    //   3. you want a guarantee of immutability — the method CAN'T
    //      mutate what the caller sees, even by accident
    //
    // map values are NOT addressable, so c.Inc() on a map's struct
    // value would NOT compile — another reason pointer receivers
    // (with pointers stored in the map) are the common default.
}
