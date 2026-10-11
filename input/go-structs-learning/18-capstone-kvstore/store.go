// ============================================================================
// CAPSTONE — store.go
// ============================================================================
//
// A production-shaped, generic, thread-safe in-memory KV store. One
// program combining the whole course:
//
//     ex. 08  unexported fields + New() constructor that validates
//     ex. 09  interface + the func-adapter pattern (http.HandlerFunc)
//     ex. 10  generic struct Store[K, V] with constraints
//     ex. 11  sync.RWMutex guarding shared state
//     ex. 12  functional options for configuration
//     ex. 16  struct tags validated through reflection
//     ex. 17  defensive snapshotting (never leak internal maps)
//
package main

import (
    "errors"
    "fmt"
    "sync"
)

// ----------------------------------------------------------------------------
// SENTINEL ERROR
// ----------------------------------------------------------------------------
//
// A package-level error VALUE that callers match with errors.Is:
//
//     if errors.Is(err, ErrFull) { ... }
//
// Never compare err.Error() strings — sentinels survive wrapping
// (fmt.Errorf with %w), string compares don't.
var ErrFull = errors.New("store is at maximum capacity")

// ----------------------------------------------------------------------------
// CONFIG — the tag-validated half
// ----------------------------------------------------------------------------
//
// Deliberately SPLIT: reflection (ex. 16) understands only plain
// data. The validator HOOK (a function/interface) lives outside
// Config because you can't put behavior in a reflection-driven tag.
type Config struct {
    Name    string `validate:"required,max=64"`
    MaxSize int    `validate:"min=1,max=1000000"`
}

// ----------------------------------------------------------------------------
// VALIDATOR — interface + function adapter (ex. 09/15 combined)
// ----------------------------------------------------------------------------
//
// An INTERFACE (not just a func type) lets callers supply stateful
// validators — rate limiters, audit loggers — as structs.
type Validator[K comparable, V any] interface {
    Validate(k K, v V) error
}

// ValidatorFunc adapts an ordinary function to the interface —
// the same trick as http.HandlerFunc: the adapter's method calls
// itself-as-a-function. Now closures like validateUser satisfy
// Validator with zero ceremony.
type ValidatorFunc[K comparable, V any] func(K, V) error

func (f ValidatorFunc[K, V]) Validate(k K, v V) error { return f(k, v) }

// ----------------------------------------------------------------------------
// OPTIONS — ex. 12, generalized over [K, V]
// ----------------------------------------------------------------------------
type settings[K comparable, V any] struct {
    cfg       Config
    validator Validator[K, V]
}

// Option mutates settings; each WithXxx returns a closure capturing
// the caller's argument.
type Option[K comparable, V any] func(*settings[K, V])

// GENERICS + INFERENCE GOTCHA:
//
// WithName's PARAMETERS never mention K or V — they appear only in
// the RESULT type. Inference works from arguments, so callers MUST
// write the type arguments explicitly:
//
//     WithName[string, User]("users")     // required
//
// WithValidator DOES infer: its fn parameter mentions both K and V,
// so WithValidator(validateUser) needs no explicit types. Compare
// the two call sites in main.go.
func WithName[K comparable, V any](n string) Option[K, V] {
    return func(s *settings[K, V]) { s.cfg.Name = n }
}

func WithMaxSize[K comparable, V any](n int) Option[K, V] {
    return func(s *settings[K, V]) { s.cfg.MaxSize = n }
}

func WithValidator[K comparable, V any](fn func(K, V) error) Option[K, V] {
    return func(s *settings[K, V]) { s.validator = ValidatorFunc[K, V](fn) }
}

// ----------------------------------------------------------------------------
// THE STORE
// ----------------------------------------------------------------------------
//
// Every field is unexported. There is NO way to construct or touch a
// Store except through New() and the methods — so the invariants
// (capacity limit, validation, locking) are enforced in exactly one
// place each and CANNOT be bypassed. That is the whole point of
// example 08's pattern, scaled up.
type Store[K comparable, V any] struct {
    mu        sync.RWMutex // GUARDS: data (never copy the Store!)
    data      map[K]V
    max       int
    validator Validator[K, V] // may be nil — "no validation"
    name      string          // immutable after New() -> lock-free reads
}

// New is the ONLY constructor:
//
//   1. start from defaults
//   2. apply options in order (later overrides earlier)
//   3. validate the assembled Config ONCE, HERE
//
// Options are dumb setters on purpose — validating in New means
// there is exactly one place that can reject a config.
func New[K comparable, V any](opts ...Option[K, V]) (*Store[K, V], error) {
    s := settings[K, V]{cfg: Config{Name: "kvstore", MaxSize: 1000}}
    for _, o := range opts {
        o(&s)
    }
    if err := ValidateStruct(s.cfg); err != nil {
        return nil, fmt.Errorf("invalid config: %w", err) // %w wraps: errors.Is works
    }
    // Deliberately NOT make(map, MaxSize) — MaxSize could be a
    // million for a store holding three entries.
    return &Store[K, V]{
        data:      make(map[K]V),
        max:       s.cfg.MaxSize,
        validator: s.validator,
        name:      s.cfg.Name,
    }, nil
}

// Set inserts or replaces one entry.
func (st *Store[K, V]) Set(key K, value V) error {
    // ------------------------------------------------------------------------
    // LOCK-SCOPE RULE: validate OUTSIDE the lock.
    // ------------------------------------------------------------------------
    // The validator is arbitrary user code — possibly slow, possibly
    // calling back into the store (-> deadlock if we held the lock).
    // Hold locks for the shortest possible critical section.
    if st.validator != nil {
        if err := st.validator.Validate(key, value); err != nil {
            return fmt.Errorf("key %v: %w", key, err)
        }
    }
    st.mu.Lock()
    defer st.mu.Unlock()
    // Overwriting an existing key doesn't grow the store — allowed
    // even at capacity:
    if _, exists := st.data[key]; !exists && len(st.data) >= st.max {
        return ErrFull
    }
    st.data[key] = value
    return nil
}

// Get returns (value, ok) — the map-native idiom, generalized.
func (st *Store[K, V]) Get(key K) (V, bool) {
    st.mu.RLock() // RLock: unlimited concurrent readers
    defer st.mu.RUnlock()
    v, ok := st.data[key]
    return v, ok
}

func (st *Store[K, V]) Delete(key K) bool {
    st.mu.Lock()
    defer st.mu.Unlock()
    if _, ok := st.data[key]; !ok {
        return false
    }
    delete(st.data, key)
    return true
}

func (st *Store[K, V]) Len() int {
    st.mu.RLock()
    defer st.mu.RUnlock()
    return len(st.data)
}

// Items returns a SNAPSHOT — a brand-new map. Handing out the
// internal map would leak shared mutable state: any caller could
// mutate it (and race with writers). Gotcha 1 of example 17, fixed.
//
// Note the depth: ONE level. If V itself contains slices/maps,
// those are still shared — document that, or deep-copy too.
func (st *Store[K, V]) Items() map[K]V {
    st.mu.RLock()
    defer st.mu.RUnlock()
    out := make(map[K]V, len(st.data))
    for k, v := range st.data {
        out[k] = v
    }
    return out
}

// String satisfies fmt.Stringer (ex. 08). Safe without the lock:
// name is immutable after New, and Len takes its own read lock
// (never nest locks here — RLock is re-entrant-safe in practice
// but nesting readers with a pending writer risks deadlock).
func (st *Store[K, V]) String() string {
    return fmt.Sprintf("%s[len=%d]", st.name, st.Len())
}
