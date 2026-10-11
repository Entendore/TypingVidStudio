// ============================================================================
// EXAMPLE 17 — FOUR STRUCT GOTCHAS THAT BITE ALMOST EVERYONE
// ============================================================================
//
// Each trap below: looks reasonable, compiles, runs — and silently
// does the wrong thing. Recognizing them on sight is the skill.
package main

import "fmt"

type Config struct {
    Name  string
    Tags  []string          // slice = small HEADER + SHARED backing array
    Extra map[string]string // map   = pointer + shared storage
}

type Point struct{ X, Y int }

func main() {
    // ------------------------------------------------------------------------
    // GOTCHA 1: copying a struct does NOT deep-copy slices/maps
    // ------------------------------------------------------------------------
    //
    // The copy duplicates the slice HEADER (ptr, len, cap) — not the
    // array behind it. Both structs end up pointing at ONE array:
    //
    //     a.Tags ──┐
    //              ├──> [ "prod" ]      one backing array
    //     b.Tags ──┘                    two headers
    //
    a := Config{
        Name:  "api",
        Tags:  []string{"prod"},
        Extra: map[string]string{"env": "prod"},
    }
    b := a // struct copied — slice/map SHARED

    b.Name = "copy"        // independent (plain string field)
    b.Tags[0] = "mutated"  // through b's header -> a.Tags CHANGED too
    b.Extra["env"] = "v2"  // same story for the map

    fmt.Println("a:", a) // {api [mutated] map[env:v2]} — surprised?
    fmt.Println("b:", b)
    //
    // FIX: hand-write a Clone() that copies Tags/Extra explicitly:
    //     func (c Config) Clone() Config {
    //         tags := append([]string(nil), c.Tags...)
    //         extra := make(map[string]string, len(c.Extra))
    //         for k, v := range c.Extra { extra[k] = v }
    //         return Config{c.Name, tags, extra}
    //     }
    // Example 18's Items() method is this exact idea, mutex-guarded.

    // ------------------------------------------------------------------------
    // GOTCHA 2: `range` hands you a COPY of each element
    // ------------------------------------------------------------------------
    //
    //     for _, p := range pts    —  p is a fresh copy per iteration
    //
    // Writing to p mutates the copy; the slice never changes. (Go
    // 1.22 fixed loop-VARIABLE capture, but the element is still a
    // copy — assignment never writes through to the slice.)
    pts := []Point{{1, 1}, {2, 2}, {3, 3}}

    for _, p := range pts {
        p.X *= 10 // mutates the copy — lost on the next iteration
    }
    fmt.Println("after range copy: ", pts) // [{1 1} {2 2} {3 3}]

    for i := range pts {
        pts[i].X *= 10 // mutate THROUGH THE INDEX — actually writes
    }
    fmt.Println("after index write: ", pts) // [{10 1} {20 2} {30 3}]

    // ------------------------------------------------------------------------
    // GOTCHA 3: pointers INTO a slice die when append reallocates
    // ------------------------------------------------------------------------
    //
    // append may grow beyond capacity -> allocate a NEW backing
    // array -> copy everything over. The slice variable is re-pointed
    // to the new array... but YOUR pointer still aims at the OLD one:
    //
    //     before: nums ──> [ {1,2} ]               cap 1
    //     after:  nums ──> [ {1,2} {9,9} ]         new array, cap 2
    //             first ──> [ {1,2} ]              fossil in the old array
    //
    nums := []Point{{1, 2}}
    first := &nums[0]

    nums = append(nums, Point{9, 9}) // reallocation happens here

    first.X = 100                    // mutates the fossil array
    fmt.Println("fossil:", *first)   // {100 2}
    fmt.Println("nums:   ", nums)    // [{1 2} {9 9}] — UNCHANGED!
    //
    // FIX: need stable identity across growth? Use a slice of
    // POINTERS ([]*Point) — the pointers themselves are copied on
    // realloc, but they aim at the same elements.

    // ------------------------------------------------------------------------
    // GOTCHA 4: a nil map field PANICS on write (reads are fine)
    // ------------------------------------------------------------------------
    //
    // A struct's map field starts as nil (zero value). Reads from a
    // nil map return zero values — but WRITES panic:
    //
    //     panic: assignment to entry in nil map
    //
    type Store struct{ data map[string]int }

    s := Store{}
    // s.data["x"] = 1              // PANIC — the trap line
    fmt.Println("nil map read:", s.data["x"], "(reads are safe: 0)")

    s.data = make(map[string]int) // initialize before first write
    s.data["x"] = 1
    fmt.Println("after make:   ", s.data)
    //
    // FIX: constructors initialize map/slice fields (example 08's
    // NewAccount pattern) so callers can never hold an un-initialized
    // struct. This is a big reason NewXxx constructors exist.
}
