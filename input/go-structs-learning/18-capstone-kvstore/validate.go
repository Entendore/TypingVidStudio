// ============================================================================
// CAPSTONE — validate.go
// ============================================================================
//
// The mini-validator from example 16, promoted from teaching demo to
// real infrastructure. Differences from the demo:
//
//   * returns a single error (errors.Join) instead of []string
//   * used by the store to guard its Config AND its values
//
// Supported rules:  required | min=N | max=N | oneof=a|b|c
package main

import (
    "errors"
    "fmt"
    "reflect"
    "strconv"
    "strings"
)

// ValidateStruct checks every exported field of a struct against its
// `validate:"..."` tag. It returns ALL violations at once, joined by
// errors.Join — the caller sees every problem in one shot instead of
// fixing one field at a time.
func ValidateStruct(v any) error {
    rv := reflect.ValueOf(v)
    if rv.Kind() == reflect.Pointer {
        rv = rv.Elem() // accept both T and *T
    }
    if rv.Kind() != reflect.Struct {
        return fmt.Errorf("validate: want struct, got %s", rv.Kind())
    }

    rt := rv.Type()
    var errs []error
    for i := 0; i < rt.NumField(); i++ {
        f := rv.Field(i)
        if !f.CanInterface() {
            continue // unexported — skip (reflection can't read it)
        }
        for _, rule := range strings.Split(rt.Field(i).Tag.Get("validate"), ",") {
            if msg := checkRule(rule, f, rt.Field(i).Name); msg != "" {
                errs = append(errs, errors.New(msg))
            }
        }
    }
    return errors.Join(errs...) // nil when errs is empty
}

func checkRule(rule string, f reflect.Value, name string) string {
    switch {
    case rule == "required":
        if f.IsZero() {
            return name + " is required"
        }

    case strings.HasPrefix(rule, "min="):
        n := atoi(rule[4:])
        if num, ok := num64(f); ok && num < float64(n) {
            return fmt.Sprintf("%s must be >= %d", name, n)
        }
        if f.Kind() == reflect.String && len(f.String()) < n {
            return fmt.Sprintf("%s must be at least %d chars", name, n)
        }

    case strings.HasPrefix(rule, "max="):
        n := atoi(rule[4:])
        if num, ok := num64(f); ok && num > float64(n) {
            return fmt.Sprintf("%s must be <= %d", name, n)
        }
        if f.Kind() == reflect.String && len(f.String()) > n {
            return fmt.Sprintf("%s must be at most %d chars", name, n)
        }

    case strings.HasPrefix(rule, "oneof="):
        if f.Kind() == reflect.String {
            for _, a := range strings.Split(rule[6:], "|") {
                if f.String() == a {
                    return ""
                }
            }
            return fmt.Sprintf("%s must be one of %s",
                name, strings.ReplaceAll(rule[6:], "|", ","))
        }
    }
    return ""
}

func num64(f reflect.Value) (float64, bool) {
    switch f.Kind() {
    case reflect.Int, reflect.Int8, reflect.Int16, reflect.Int32, reflect.Int64:
        return float64(f.Int()), true
    case reflect.Uint, reflect.Uint8, reflect.Uint16, reflect.Uint32, reflect.Uint64:
        return float64(f.Uint()), true
    case reflect.Float32, reflect.Float64:
        return f.Float(), true
    }
    return 0, false
}

func atoi(s string) int {
    n, _ := strconv.Atoi(s)
    return n
}
