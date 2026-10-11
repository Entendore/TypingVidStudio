// ============================================================================
// CAPSTONE — store_test.go
// ============================================================================
//
//   go test ./18-capstone-kvstore
//   go test -race ./18-capstone-kvstore   <- the important one
//
// The -race build instruments every memory access; if any two
// goroutines race, the test fails with both stacks printed.
package main

import (
    "errors"
    "fmt"
    "sync"
    "testing"
)

func mustStore(t *testing.T, opts ...Option[string, int]) *Store[string, int] {
    t.Helper() // failures report the caller's line, not in here
    s, err := New(opts...)
    if err != nil {
        t.Fatal(err)
    }
    return s
}

func die(t *testing.T, err error) {
    t.Helper()
    if err != nil {
        t.Fatal(err)
    }
}

func TestConfigValidation(t *testing.T) {
    // The Config's own tags are enforced by New — MaxSize=0 breaks min=1.
    if _, err := New[string, int](WithMaxSize[string, int](0)); err == nil {
        t.Fatal("MaxSize=0 must be rejected")
    }
}

func TestSetGetDelete(t *testing.T) {
    s := mustStore(t)

    die(t, s.Set("a", 1))
    if v, ok := s.Get("a"); !ok || v != 1 {
        t.Fatalf("Get(a) = (%v, %v), want (1, true)", v, ok)
    }
    if !s.Delete("a") {
        t.Fatal("Delete(existing) = false")
    }
    if s.Delete("a") {
        t.Fatal("Delete(missing) = true")
    }
    if s.Len() != 0 {
        t.Fatalf("Len = %d, want 0", s.Len())
    }
}

func TestMaxSize(t *testing.T) {
    s := mustStore(t, WithMaxSize[string, int](2))

    die(t, s.Set("a", 1))
    die(t, s.Set("b", 2))
    if err := s.Set("c", 3); !errors.Is(err, ErrFull) {
        t.Fatalf("want ErrFull, got %v", err)
    }
    // Overwrite at capacity is NOT growth — must succeed:
    die(t, s.Set("a", 100))
    if v, _ := s.Get("a"); v != 100 {
        t.Fatalf("overwrite didn't take: Get(a) = %d", v)
    }
}

func TestValidator(t *testing.T) {
    s, err := New[string, int](WithValidator(func(_ string, v int) error {
        if v%2 != 0 {
            return fmt.Errorf("odd: %d", v)
        }
        return nil
    }))
    if err != nil {
        t.Fatal(err)
    }
    die(t, s.Set("ok", 4))
    if err := s.Set("bad", 3); err == nil {
        t.Fatal("validator must reject odd values")
    }
    // A rejected value must leave NO trace:
    if _, ok := s.Get("bad"); ok {
        t.Fatal("rejected value was stored anyway")
    }
}

func TestSnapshotIsolation(t *testing.T) {
    s := mustStore(t)
    die(t, s.Set("a", 1))

    snap := s.Items()
    snap["a"] = 999  // tamper with the snapshot...
    snap["ghost"] = 1 // ...and add to it

    // Neither may leak into the store:
    if v, _ := s.Get("a"); v != 1 {
        t.Fatal("snapshot mutation leaked into the store")
    }
    if s.Len() != 1 {
        t.Fatal("snapshot insertion leaked into the store")
    }
}

func TestOtherTypes(t *testing.T) {
    // Only K must be comparable. V can be ANYTHING — here a slice,
    // which isn't even ==-comparable. Generics don't restrict V.
    s, err := New[int, []string](WithName[int, []string]("logs"))
    if err != nil {
        t.Fatal(err)
    }
    die(t, s.Set(1, []string{"hello", "world"}))
    if v, ok := s.Get(1); !ok || len(v) != 2 {
        t.Fatalf("Get(1) = (%v, %v)", v, ok)
    }
}

func TestConcurrentSets(t *testing.T) {
    s, err := New[int, int](WithMaxSize[int, int](1000000))
    if err != nil {
        t.Fatal(err)
    }

    const workers, perWorker = 50, 200
    var wg sync.WaitGroup
    for w := 0; w < workers; w++ {
        wg.Add(1)
        go func(w int) {
            defer wg.Done()
            for i := 0; i < perWorker; i++ {
                // t.Error is goroutine-safe; t.Fatal is NOT —
                // Fatal must only run on the test's goroutine.
                if err := s.Set(w*perWorker+i, i); err != nil {
                    t.Error(err)
                }
            }
        }(w)
    }
    wg.Wait()

    if want := workers * perWorker; s.Len() != want {
        t.Fatalf("Len = %d, want %d (lost updates? run with -race)", s.Len(), want)
    }
}
