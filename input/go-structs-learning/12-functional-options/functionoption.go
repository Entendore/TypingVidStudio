// ============================================================================
// EXAMPLE 12 — FUNCTIONAL OPTIONS PATTERN
// ============================================================================
//
// Go has no optional or named parameters. When a constructor grows
// past two or three settings you have four choices:
//
//   1. NewServer(host, port, timeout, maxConn, tls, log, ...) —
//      positional wall; every caller must know every default
//   2. multiple constructors (NewServer, NewServerTLS...) — explodes
//   3. exported config struct — zero values must BE correct defaults,
//      and fields become part of your public API forever
//   4. FUNCTIONAL OPTIONS — the pattern used by gRPC, most DB
//      drivers, and half the ecosystem:
//
//         NewServer("api.example.com",
//             WithPort(443),
//             WithTimeout(5*time.Second),
//         )
//
// ANATOMY — three pieces:
//
//   type Option func(*Server)          1. the option TYPE: a closure
//                                      that mutates the config
//   func WithXxx(...) Option { ... }   2. WithXxx BUILDERS: capture
//                                      args, return the closure
//   func New(host, opts ...Option)     3. variadic constructor:
//                                      defaults first, apply options
//
package main

import (
    "fmt"
    "time"
)

type Server struct {
    host    string
    port    int
    timeout time.Duration
    maxConn int
}

// ----------------------------------------------------------------------------
// 1) THE OPTION TYPE — a function that mutates the config
// ----------------------------------------------------------------------------
type Option func(*Server)

// ----------------------------------------------------------------------------
// 2) WithXxx BUILDERS — each returns a closure capturing its argument
// ----------------------------------------------------------------------------
//
// Note the shape: WithTimeout(d) runs NOW (returns the closure);
// the closure itself runs LATER, inside NewServer.
func WithPort(p int) Option {
    return func(s *Server) { s.port = p }
}

func WithTimeout(d time.Duration) Option {
    return func(s *Server) { s.timeout = d }
}

func WithMaxConn(n int) Option {
    return func(s *Server) { s.maxConn = n }
}

// ----------------------------------------------------------------------------
// 3) THE CONSTRUCTOR — defaults, then options in order
// ----------------------------------------------------------------------------
//
// Options apply IN ORDER, so a later option overrides an earlier one.
// Adding a new option later breaks NO existing caller — that
// backward compatibility is the pattern's main selling point.
func NewServer(host string, opts ...Option) *Server {
    s := &Server{
        host:    host,
        port:    8080,             // defaults live HERE, in one place
        timeout: 30 * time.Second,
        maxConn: 100,
    }
    for _, opt := range opts {
        opt(s)
    }
    return s
}

func main() {
    // No options — all defaults:
    fmt.Printf("%+v\n", NewServer("localhost"))

    // Override only what you need; defaults fill the rest:
    fmt.Printf("%+v\n", NewServer("api.example.com",
        WithPort(443),
        WithTimeout(5*time.Second),
    ))

    // Options are ORDINARY VALUES — build, store, compose, reuse:
    turbo := []Option{WithMaxConn(1000), WithPort(9090)}
    fmt.Printf("%+v\n", NewServer("hot", turbo...))

    // -------------------------------------------------------------------
    // HONEST TRADE-OFFS (nothing is free)
    // -------------------------------------------------------------------
    //
    //   * boilerplate: every option is 3 lines + doc comment
    //   * typos in WithXxx names can't be caught by the compiler
    //     against the struct (they're just functions)
    //   * for 2-3 settings, or where zero values ARE the defaults,
    //     an exported config struct is simpler:
    //
    //         type Config struct { Port int; Timeout time.Duration }
    //         New(Config{Port: 443})
    //
    // Rule of thumb: library/infrastructure code -> options;
    // application code with few knobs -> config struct.
}
