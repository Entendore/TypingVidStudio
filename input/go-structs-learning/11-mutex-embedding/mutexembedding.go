// ============================================================================
// EXAMPLE 11 — EMBEDDING sync.Mutex: CONCURRENCY-SAFE STRUCTS
// ============================================================================
//
// A DATA RACE: two goroutines access the same memory, at least one
// writes, with no synchronization. Races cause corrupted state and
// crashes that appear weeks later in production. The standard fix
// for struct fields: a sync.Mutex guarding all access.
//
//   sync.RWMutex = readers/writers lock:
//     Lock()    — exclusive: no readers, no other writers
//     RLock()   — shared: many readers at once, but blocks writers
//
// TWO IDIOMS for placing the mutex:
//
//     mu sync.Mutex   -> named:   v.mu.Lock()  (intent is explicit)
//     sync.Mutex      -> embedded: v.Lock()    (promoted method)
//
// Both appear in the standard library. Named is more common in
// application code.
package main

import (
    "fmt"
    "sync"
)

type Visits struct {
    mu     sync.Mutex // GUARDS: counts (see doc comment convention)
    counts map[string]int
}

func NewVisits() *Visits {
    // Constructor returns a POINTER — mandatory here (see the
    // copy warning at the bottom of main).
    return &Visits{counts: make(map[string]int)}
}

// ----------------------------------------------------------------------------
// EVERY method that touches guarded fields locks FIRST.
// ----------------------------------------------------------------------------
//
// The pattern is always the same two lines:
//
//     v.mu.Lock()
//     defer v.mu.Unlock()
//
// defer guarantees release on EVERY exit path — early returns,
// panics — so you can't forget. For tiny critical sections the
// defer costs little; measure before hand-unrolling it.
func (v *Visits) Record(page string) {
    v.mu.Lock()
    defer v.mu.Unlock()
    v.counts[page]++ // map writes are NOT atomic — this is the race
}

// Reads also need the lock: a reader racing a writer is still a race.
func (v *Visits) Count(page string) int {
    v.mu.Lock()
    defer v.mu.Unlock()
    return v.counts[page]
}

// ----------------------------------------------------------------------------
// EMBEDDED mutex — Lock/Unlock are promoted to Session
// ----------------------------------------------------------------------------
type Session struct {
    sync.Mutex // embedded: s.Lock() works directly
    User       string
}

func main() {
    v := NewVisits()

    // ------------------------------------------------------------------------
    // 100 goroutines hammering the same map
    // ------------------------------------------------------------------------
    //
    // Delete the two mu.Lock/Unlock lines and this program becomes
    // a textbook data race — sometimes it crashes, usually it just
    // silently miscounts. PROVE it:
    //
    //     go run -race ./11-mutex-embedding
    //
    // The race detector instruments memory access and reports the
    // exact two conflicting stacks. Use it on every test run in CI.
    //
    var wg sync.WaitGroup
    for i := 0; i < 100; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            v.Record("/home")
        }()
    }
    wg.Wait()
    fmt.Println("/home visits:", v.Count("/home")) // 100, every run

    // ------------------------------------------------------------------------
    // EMBEDDED mutex in action
    // ------------------------------------------------------------------------
    s := Session{User: "ada"}
    s.Lock() // promoted from the embedded sync.Mutex
    s.User = "grace"
    s.Unlock()
    fmt.Println("user:", s.User)

    // ------------------------------------------------------------------------
    // !!! THE BIG WARNING: NEVER COPY A CONTAINED MUTEX !!!
    // ------------------------------------------------------------------------
    //
    // A mutex is a MACHINE, not data. After a copy, both structs
    // think they hold the same lock but don't — races and deadlocks.
    //
    //     bad := *v              // copy — WRONG
    //     func f(x Visits)       // by-value arg — copies — WRONG
    //     func g() Visits        // returning by value — WRONG
    //
    // RULES:
    //   * share these structs by POINTER (*Visits) everywhere
    //   * constructors return pointers (NewVisits above)
    //   * `go vet ./...` has a "copylocks" check that catches
    //     violations — run vet in CI, always
    //
    // Convention: if a struct contains a mutex, document it at the
    // top: "Visits must not be copied after first use."
}
