// ============================================================================
// CAPSTONE — main.go (the demo driver)
// ============================================================================
//
// The store knows NOTHING about User — validation rules live in the
// User type's tags and in a closure. That inversion is what makes
// the store reusable: swap the types and validator, keep the store.
//
// Rule placement strategy:
//   per-field rules   -> tags        ("required", "min=0", "oneof=...")
//   cross-field rules -> closures    ("admins must be 18+")
package main

import (
    "errors"
    "fmt"
    "sync"
)

type User struct {
    Name string `validate:"required,min=2,max=32"`
    Age  int    `validate:"min=0,max=150"`
    Role string `validate:"oneof=admin|user|guest"`
}

// Cross-field rule — awkward in per-field tags, natural in a closure.
// Signature matches ValidatorFunc, so it plugs straight in.
func adminsMustBeAdults(_ string, u User) error {
    if u.Role == "admin" && u.Age < 18 {
        return fmt.Errorf("admin %q is %d — must be 18+", u.Name, u.Age)
    }
    return nil
}

// validateUser CHAINS checks: tag rules first, then cross-field.
// Composition of small checks beats one giant validate function.
func validateUser(k string, u User) error {
    if err := ValidateStruct(u); err != nil {
        return err
    }
    return adminsMustBeAdults(k, u)
}

func die(err error) {
    if err != nil {
        panic(err)
    }
}

func main() {
    // ------------------------------------------------------------------------
    // 1) CONSTRUCTION — explicit type args on WithName/WithMaxSize
    //    (their params never mention K/V — see store.go), inferred
    //    on WithValidator (its fn param does mention them).
    // ------------------------------------------------------------------------
    store, err := New[string, User](
        WithName[string, User]("users"),
        WithMaxSize[string, User](3),
        WithValidator(validateUser), // no explicit type args needed!
    )
    die(err)
    fmt.Println("built:        ", store)

    // ------------------------------------------------------------------------
    // 2) THE CONFIG ITSELF IS TAG-VALIDATED — MaxSize=0 violates min=1
    // ------------------------------------------------------------------------
    _, err = New[string, User](WithMaxSize[string, User](0))
    fmt.Println("bad config:   ", err)

    // ------------------------------------------------------------------------
    // 3) TAG RULES reject the value before it's stored
    // ------------------------------------------------------------------------
    err = store.Set("x", User{Name: "A", Age: 200, Role: "wizard"})
    fmt.Println("bad value:    ", err)

    // ------------------------------------------------------------------------
    // 4) HAPPY PATH
    // ------------------------------------------------------------------------
    die(store.Set("ada", User{Name: "Ada", Age: 36, Role: "admin"}))
    die(store.Set("bob", User{Name: "Bob", Age: 17, Role: "user"}))

    // ------------------------------------------------------------------------
    // 5) THE CLOSURE'S CROSS-FIELD RULE fires
    // ------------------------------------------------------------------------
    err = store.Set("carol", User{Name: "Carol", Age: 9, Role: "admin"})
    fmt.Println("cross-field:  ", err)

    // ------------------------------------------------------------------------
    // 6) CAPACITY — matched via the SENTINEL error (errors.Is)
    // ------------------------------------------------------------------------
    die(store.Set("dave", User{Name: "Dave", Age: 40, Role: "guest"}))
    err = store.Set("eve", User{Name: "Eve", Age: 28, Role: "user"})
    if errors.Is(err, ErrFull) {
        fmt.Println("capacity:     ", err)
    }

    // ------------------------------------------------------------------------
    // 7) GET / DELETE churn
    // ------------------------------------------------------------------------
    if u, ok := store.Get("ada"); ok {
        fmt.Printf("get ada:      %+v\n", u)
    }
    if _, ok := store.Get("zed"); !ok {
        fmt.Println("get zed:      miss -> (zero value, false)")
    }
    store.Delete("bob") // frees a slot...
    die(store.Set("eve", User{Name: "Eve", Age: 28, Role: "user"}))
    fmt.Println("after churn:  ", store)

    // ------------------------------------------------------------------------
    // 8) SNAPSHOT ISOLATION — tamper with the copy, store unaffected
    //    (the deliberate fix for gotcha 1 in example 17)
    // ------------------------------------------------------------------------
    snap := store.Items()
    snap["ada"] = User{Name: "hacker", Age: 0, Role: "guest"}
    original, _ := store.Get("ada")
    fmt.Println("tamper-safe:  ", original.Name == "Ada") // true

    // ------------------------------------------------------------------------
    // 9) CONCURRENCY — 50 goroutines x 200 writes under RWMutex
    // ------------------------------------------------------------------------
    counts, err := New[int, int](WithMaxSize[int, int](1000000))
    die(err)
    var wg sync.WaitGroup
    for w := 0; w < 50; w++ {
        wg.Add(1)
        go func(w int) {
            defer wg.Done()
            for i := 0; i < 200; i++ {
                die(counts.Set(w*200+i, 1))
            }
        }(w)
    }
    wg.Wait()
    fmt.Println("concurrent:   ", counts.Len(), "entries (want 10000)")
    fmt.Println("prove it:      go test -race ./18-capstone-kvstore")
}
