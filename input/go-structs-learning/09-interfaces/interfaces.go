// ============================================================================
// EXAMPLE 09 — STRUCTS SATISFYING INTERFACES (METHOD SETS)
// ============================================================================
//
// An interface is a TYPE listing required METHODS. A struct satisfies
// it implicitly by having those methods — no "implements" keyword,
// anywhere, ever.
//
// THE ONE RULE YOU MUST KNOW — method sets:
//
//     methods with VALUE receivers    -> belong to T  AND *T
//     methods with POINTER receivers  -> belong to *T ONLY
//
// So if ANY interface method has a pointer receiver, only the
// POINTER satisfies the interface. The value does not.
//
//     ┌────────────────────────┬───────────────┬──────────────┐
//     │ receiver of Speak()    │ Speaker(Dog)  │ Speaker(*Dog)│
//     ├────────────────────────┼───────────────┼──────────────┤
//     │ func (d Dog) Speak()   │     yes       │     yes      │
//     │ func (d *Dog) Speak()  │     NO        │     yes      │
//     └────────────────────────┴───────────────┴──────────────┘
//
// WHY: you can always take an address (&d), but you can't always
// take the value's address back from a pointer — so the compiler
// can't synthesize the missing half. Example 03 explains the cause.
package main

import "fmt"

type Speaker interface {
    Speak() string
}

type Dog struct {
    Name string
}

// VALUE receiver: both Dog and *Dog satisfy Speaker.
func (d Dog) Speak() string {
    return d.Name + ": woof!"
}

type Robot struct {
    ID int
}

// POINTER receiver: only *Robot satisfies Speaker. Robot (the value)
// does NOT.
func (r *Robot) Speak() string {
    return fmt.Sprintf("robot-%d: beep", r.ID)
}

// Program against BEHAVIOR, not concrete types — the entire point
// of interfaces. announce accepts anything that can Speak.
func announce(s Speaker) {
    fmt.Println(s.Speak())
}

func main() {
    d := Dog{Name: "Rex"}
    announce(d)  // Dog works   (value receiver)
    announce(&d) // *Dog works too

    r := Robot{ID: 7}
    announce(&r) // *Robot works
    // announce(r) // COMPILE ERROR:
    //             //   Robot does not implement Speaker
    //             //   (method Speak has pointer receiver)

    // ------------------------------------------------------------------------
    // GOTCHA: nil INTERFACE vs interface holding a NIL POINTER
    // ------------------------------------------------------------------------
    //
    // An interface value is a (dynamic type, dynamic value) pair.
    // It is nil ONLY when BOTH are nil. A nil *Robot WRAPPED in the
    // interface has type *Robot — so the interface is NOT nil, even
    // though it holds a nil pointer. This bites everyone once.
    var nr *Robot          // nil *Robot
    var sp Speaker = nr    // wraps (type=*Robot, value=nil)
    fmt.Println("sp == nil:", sp == nil) // FALSE — surprise!
    // sp.Speak() here would PANIC: Speak dereferences r.ID on nil.

    // ------------------------------------------------------------------------
    // TYPE SWITCH — discover the dynamic type
    // ------------------------------------------------------------------------
    var s Speaker = &r
    switch v := s.(type) {
    case *Robot:
        fmt.Println("it's a *Robot, id", v.ID) // v is *Robot here
    case Dog:
        fmt.Println("it's a Dog,", v.Name) // v is Dog here
    }

    // ------------------------------------------------------------------------
    // `any` — the empty interface
    // ------------------------------------------------------------------------
    // `any` (alias for interface{} since 1.18) is satisfied by ALL
    // types. Useful for fmt-style plumbing, but you lose compile-time
    // checks — prefer the smallest interface that works.
    fmt.Printf("dynamic type: %T\n", any(Dog{})) // main.Dog
}
