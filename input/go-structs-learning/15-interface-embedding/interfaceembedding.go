// ============================================================================
// EXAMPLE 15 — EMBEDDING INTERFACES: DECORATORS & PARTIAL MOCKS
// ============================================================================
//
// You can embed an INTERFACE in a struct. The interface's methods are
// PROMOTED to the struct, so by default every call is DELEGATED to
// the embedded value — and the struct overrides only the methods it
// wants to change:
//
//     type TimestampLogger struct {
//         Logger            // embedded interface — the wrapped component
//     }
//     func (t TimestampLogger) Info(msg string) { ... }  // override
//                                                        // Error: delegated
//
// This one mechanism powers two huge real-world patterns:
//
//   1. DECORATORS / MIDDLEWARE — wrap a component, add one behavior
//      (timing, logging, retries), pass the wrapper on. HTTP
//      middleware is exactly this with http.ResponseWriter.
//
//   2. PARTIAL TEST MOCKS — override ONE method to capture calls,
//      let the rest fall through to the real implementation.
//
package main

import (
    "fmt"
    "time"
)

// ----------------------------------------------------------------------------
// The component everyone depends on (the interface)
// ----------------------------------------------------------------------------
type Logger interface {
    Info(msg string)
    Error(msg string)
}

// A concrete implementation:
type ConsoleLogger struct {
    Prefix string
}

func (c ConsoleLogger) Info(msg string)  { fmt.Println(c.Prefix, "INFO ", msg) }
func (c ConsoleLogger) Error(msg string) { fmt.Println(c.Prefix, "ERROR", msg) }

// ----------------------------------------------------------------------------
// DECORATOR 1: timestamps on Info; Error is PROMOTED (delegated)
// ----------------------------------------------------------------------------
//
// TimestampLogger does NOT define Error — so t.Error(...) is
// promoted to t.Logger.Error(...) automatically. We wrapped the
// component by writing ONE method.
type TimestampLogger struct {
    Logger // embedded interface
}

func (t TimestampLogger) Info(msg string) {
    t.Logger.Info(time.Now().Format("15:04:05") + " | " + msg)
}

// ----------------------------------------------------------------------------
// DECORATOR 2: counts calls, then delegates
// ----------------------------------------------------------------------------
//
// Because CountingLogger still implements Logger (its own Info/Error),
// it can wrap ANOTHER decorator — chains compose without limit.
type CountingLogger struct {
    Logger
    infos, errors int
}

func (c *CountingLogger) Info(msg string)  { c.infos++; c.Logger.Info(msg) }
func (c *CountingLogger) Error(msg string) { c.errors++; c.Logger.Error(msg) }

func (c CountingLogger) Stats() string {
    return fmt.Sprintf("infos=%d errors=%d", c.infos, c.errors)
}

// ----------------------------------------------------------------------------
// PARTIAL MOCK: override ONLY Error; Info falls through to the real one
// ----------------------------------------------------------------------------
//
// In tests you pass ErrorCapture where a Logger is expected — Error
// calls are recorded, Info calls still print for debugging. This is
// how hand-rolled fakes work (and roughly what mockery generates).
type ErrorCapture struct {
    Logger
    Errors []string
}

func (e *ErrorCapture) Error(msg string) {
    e.Errors = append(e.Errors, msg)
}

// Any layer of the chain satisfies Logger — that's the contract:
func doWork(l Logger) {
    l.Info("working...")
    l.Error("demo failure")
}

func main() {
    // ------------------------------------------------------------------------
    // Build the decorator chain: console -> timestamps -> counts
    // ------------------------------------------------------------------------
    var base Logger = ConsoleLogger{"[app]"}
    timed := TimestampLogger{Logger: base}
    counted := &CountingLogger{Logger: timed}

    counted.Info("server started")
    counted.Error("db connection lost")
    counted.Info("retrying")
    fmt.Println(counted.Stats()) // infos=2 errors=1

    doWork(counted) // the chain tail still satisfies Logger

    // ------------------------------------------------------------------------
    // GOTCHA: an embedded interface starts NIL
    // ------------------------------------------------------------------------
    //
    // Field promotion gives you the method set, but the embedded
    // field itself is nil until assigned. Calling a method on it
    // panics — there is nothing behind the delegation.
    var broken TimestampLogger
    if broken.Logger == nil {
        fmt.Println("embedded Logger is nil — calling Info would panic")
    }
    // broken.Info("boom") // panic: nil pointer dereference

    // ------------------------------------------------------------------------
    // Partial mock in action
    // ------------------------------------------------------------------------
    captured := &ErrorCapture{Logger: ConsoleLogger{"[test]"}}
    captured.Info("promoted — prints via the embedded real logger")
    captured.Error("fake #1")
    captured.Error("fake #2")
    fmt.Println("captured:", captured.Errors)

    // ------------------------------------------------------------------------
    // KEY POINT
    // ------------------------------------------------------------------------
    // Delegation is free but NOT inheritance: the decorator is not a
    // ConsoleLogger and can't access its internals — only its public
    // methods. Wrap behavior, don't reach inside.
}
