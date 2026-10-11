// ============================================================================
// EXAMPLE 08 — THE CONSTRUCTOR PATTERN (NewXxx) + VALIDATION + STRINGER
// ============================================================================
//
// Go has NO constructors and NO default values. The convention:
//
//   1. keep fields UNEXPORTED so callers can't build invalid states
//   2. expose NewXxx(...) that validates and returns (*T, error)
//
// This makes the constructor the ONLY doorway in — every invariant
// ("balance is never negative", "email is present") is checked in
// exactly one place, and impossible to bypass.
package main

import (
    "errors"
    "fmt"
)

type Account struct {
    username string // unexported: code outside can't even construct
    email    string //             an Account directly
    balance  int    // INVARIANT: never negative (in cents)
}

// ----------------------------------------------------------------------------
// THE CONSTRUCTOR
// ----------------------------------------------------------------------------
//
// Idiomatic signature: (*T, error). The RULES:
//
//   * on failure  -> return (nil, err)      — never a half-built value
//   * on success  -> return (acc, nil)      — never both non-nil
//   * name it New<T>, or New for the one main type of a package
//
func NewAccount(username, email string) (*Account, error) {
    if username == "" {
        return nil, errors.New("username is required")
    }
    if email == "" {
        return nil, errors.New("email is required")
    }
    // All checks passed — only HERE does a valid Account exist.
    return &Account{username: username, email: email}, nil
}

// ----------------------------------------------------------------------------
// METHODS THAT PROTECT THE INVARIANT
// ----------------------------------------------------------------------------
//
// Deposit can't be bypassed (unexported balance), so the invariant
// "balance >= 0" is enforced in exactly two small places.
func (a *Account) Deposit(cents int) error {
    if cents <= 0 {
        return errors.New("deposit must be positive")
    }
    a.balance += cents
    return nil
}

func (a *Account) Withdraw(cents int) error {
    if cents <= 0 {
        return errors.New("withdrawal must be positive")
    }
    if cents > a.balance {
        return fmt.Errorf("insufficient funds: have %d, want %d", a.balance, cents)
    }
    a.balance -= cents
    return nil
}

// ----------------------------------------------------------------------------
// GETTERS — Go convention: NO "Get" prefix
// ----------------------------------------------------------------------------
//
// Balance, not GetBalance. Accessors that return the field are
// considered cheap enough that the prefix is pure noise.
func (a Account) Balance() int {
    return a.balance
}

// ----------------------------------------------------------------------------
// fmt.Stringer — customize how fmt prints this type
// ----------------------------------------------------------------------------
//
// Any type with method  String() string  gets it called automatically
// by fmt's %v / %s verbs. It's Go's version of __str__/toString.
func (a Account) String() string {
    return fmt.Sprintf("%s<%s> balance=%d¢", a.username, a.email, a.balance)
}

func main() {
    acc, err := NewAccount("ada", "ada@example.com")
    if err != nil {
        panic(err)
    }

    if err := acc.Deposit(2500); err != nil {
        panic(err)
    }
    if err := acc.Withdraw(500); err != nil {
        panic(err)
    }

    // fmt.Println finds String() automatically:
    fmt.Println(acc) // output: ada<ada@example.com> balance=2000¢

    // Constructor validation at work — bad input never becomes a value:
    if _, err := NewAccount("", "x@x.com"); err != nil {
        fmt.Println("rejected:", err)
    }

    // Account{} with exported fields would compile but is IMPOSSIBLE
    // to create here — the zero Account is unreachable from outside.
}
