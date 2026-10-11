// ============================================================================
// EXAMPLE 10 — GENERIC STRUCTS (TYPE PARAMETERS)
// ============================================================================
//
// Since Go 1.18 a struct can take TYPE PARAMETERS — placeholders
// filled in at each use site:
//
//     type Stack[T any] struct { ... }   // T is the placeholder
//     var s Stack[int]                   // T := int at this use
//
// Wins over interface{}: full type safety, no boxing, no type
// assertions, and the compiler rejects wrong element types.
//
package main

import "fmt"

// ----------------------------------------------------------------------------
// Stack[T any] — ONE type parameter, constraint `any`
// ----------------------------------------------------------------------------
//
// [T any] reads: "T is a type parameter; any type satisfies it."
// `any` is literally an alias for interface{} used as a constraint.
//
// Note the struct literal STILL needs the type argument (&Stack[int]{})
// — there are no arguments to infer it from at construction time.
type Stack[T any] struct {
    items []T
}

// Methods REUSE the receiver's parameter: (s *Stack[T]) — they
// cannot declare new ones.
func (s *Stack[T]) Push(v T) {
    s.items = append(s.items, v)
}

// Pop returns (zero, false) when empty — the "value, ok" pattern
// generalized to any T. `var zero T` is T's zero value whatever T is:
// 0 for int, "" for string, nil for a pointer type...
func (s *Stack[T]) Pop() (T, bool) {
    var zero T
    if len(s.items) == 0 {
        return zero, false
    }
    last := s.items[len(s.items)-1]
    s.items = s.items[:len(s.items)-1]
    return last, true
}

func (s *Stack[T]) Len() int { return len(s.items) }

// ----------------------------------------------------------------------------
// Pair[K, V] — MULTIPLE parameters, each with its own constraint
// ----------------------------------------------------------------------------
//
// `comparable` is a built-in constraint: any type supporting ==/!=
// (numbers, strings, pointers, comparable structs). It exists
// precisely so K can be used as a map key inside Pair-using code.
type Pair[K comparable, V any] struct {
    Key   K
    Value V
}

// ----------------------------------------------------------------------------
// CUSTOM CONSTRAINTS = TYPE SETS
// ----------------------------------------------------------------------------
//
//     ~int | ~int64 | ~float64
//      │
//      └── ~ means "any type whose UNDERLYING type is X" — so named
//          types like `type Celsius float64` also satisfy ~float64.
//
// Without the ~, only the literal types int/int64/float64 qualify.
type Number interface {
    ~int | ~int64 | ~float64
}

// Total only accepts numeric element types — Total[string] won't
// compile, with a clear error. That's constraints doing their job.
type Total[T Number] struct {
    sum T
}

func (t *Total[T]) Add(v T) { t.sum += v }
func (t Total[T]) Sum() T   { return t.sum }

func main() {
    // ------------------------------------------------------------------------
    // TYPE INFERENCE — usually you don't write the type arguments
    // ------------------------------------------------------------------------
    //
    // Push's PARAMETER mentions T, so Go infers T from the argument:
    is := &Stack[int]{} // construction: no args -> must write [int]
    is.Push(1)          // here T is inferred: int
    is.Push(2)
    v, _ := is.Pop()
    fmt.Println("popped:", v, "| left:", is.Len()) // 2 | 1

    ss := &Stack[string]{}
    ss.Push("hello")
    fmt.Println("string stack len:", ss.Len())

    // Multiple explicit type arguments:
    p := Pair[string, float64]{Key: "pi", Value: 3.14159}
    fmt.Println(p.Key, "=", p.Value)

    t := &Total[float64]{}
    t.Add(1.5)
    t.Add(2.5)
    fmt.Println("sum:", t.Sum()) // 4

    // Total[string]{} -> compile error: string does not satisfy Number.

    // ------------------------------------------------------------------------
    // GENERICS vs INTERFACES — when to reach for which
    // ------------------------------------------------------------------------
    //
    //   generics -> same CODE, many TYPES (containers, algorithms)
    //   interface -> same CONTRACT, many BEHAVIORS (plugins, mocking)
    //
    // If you were about to write a struct holding interface{} and
    // type-asserting everywhere — that's the generics use case.
}
