// ============================================================================
// EXAMPLE 16 — CUSTOM STRUCT TAGS + REFLECTION: A MINI-VALIDATOR
// ============================================================================
//
// Tags are inert strings. The "magic" of encoding/json,
// go-playground/validator, and every ORM is the same ~150 lines of
// reflection you're about to read.
//
// REFLECTION IN 60 SECONDS:
//
//   reflect.TypeOf(v)   -> the TYPE  (field names, tags, methods)
//   reflect.ValueOf(v)  -> the VALUE (readable/writable field values)
//
//   reflect can read anything; it can WRITE only through pointers,
//   and never unexported fields (CanInterface()==false).
//
// Supported rules below:
//
//     required      field must not be the zero value
//     min=N         number >= N  (string: length >= N)
//     max=N         number <= N  (string: length <= N)
//     oneof=a|b|c   string must be one of the listed values
package main

import (
    "fmt"
    "reflect"
    "strconv"
    "strings"
)

// The `validate` tag is OUR invention — its meaning exists only
// because Validate() below parses it.
type User struct {
    Name  string `validate:"required,min=2,max=32"`
    Age   int    `validate:"min=0,max=150"`
    Email string `validate:"required"`
    Role  string `validate:"oneof=admin|user|guest"`

    // Unexported: field.CanInterface() is false, so the validator
    // skips it — reflection deliberately cannot read private state.
    secret string
}

// ----------------------------------------------------------------------------
// THE VALIDATOR — walk fields, parse tags, apply rules
// ----------------------------------------------------------------------------
func Validate(v any) []string {
    rv := reflect.ValueOf(v)
    if rv.Kind() == reflect.Pointer {
        rv = rv.Elem() // accept both User and *User
    }
    if rv.Kind() != reflect.Struct {
        return []string{"Validate: not a struct"}
    }

    rt := rv.Type() // the TYPE: field names + tags live here
    var problems []string

    for i := 0; i < rt.NumField(); i++ {
        field := rv.Field(i)          // the VALUE of field i
        sf := rt.Field(i)             // the STRUCT-FIELD metadata (name, tag)

        if !field.CanInterface() {
            continue // unexported — read-protected by design
        }

        rules := sf.Tag.Get("validate") // e.g. "required,min=2,max=32"
        if rules == "" {
            continue
        }

        // Rules are comma-separated; each is checked independently
        // so one field can report several problems at once.
        for _, rule := range strings.Split(rules, ",") {
            if msg := check(rule, field, sf.Name); msg != "" {
                problems = append(problems, msg)
            }
        }
    }
    return problems
}

// ----------------------------------------------------------------------------
// ONE rule against ONE field. Empty string == no problem.
// ----------------------------------------------------------------------------
func check(rule string, f reflect.Value, name string) string {
    switch {
    case rule == "required":
        // IsZero works for EVERY type — zero value per type, like ex. 01.
        if f.IsZero() {
            return name + " is required"
        }

    case strings.HasPrefix(rule, "min="):
        n := atoi(rule[len("min="):])
        if num, ok := num64(f); ok && num < float64(n) {
            return fmt.Sprintf("%s must be >= %d", name, n)
        }
        if f.Kind() == reflect.String && len(f.String()) < n {
            return fmt.Sprintf("%s must be at least %d chars", name, n)
        }

    case strings.HasPrefix(rule, "max="):
        n := atoi(rule[len("max="):])
        if num, ok := num64(f); ok && num > float64(n) {
            return fmt.Sprintf("%s must be <= %d", name, n)
        }
        if f.Kind() == reflect.String && len(f.String()) > n {
            return fmt.Sprintf("%s must be at most %d chars", name, n)
        }

    case strings.HasPrefix(rule, "oneof="):
        if f.Kind() != reflect.String {
            return "" // rule silently inapplicable to this kind
        }
        allowed := strings.Split(rule[len("oneof="):], "|")
        for _, a := range allowed {
            if f.String() == a {
                return ""
            }
        }
        return fmt.Sprintf("%s must be one of: %s", name, strings.Join(allowed, ", "))
    }
    return ""
}

// num64 normalizes any int/uint/float KIND to float64.
// f.Kind() is the UNDERLYING kind — it sees through named types.
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
    n, _ := strconv.Atoi(s) // a malformed tag yields 0 — real libs
    return n                // report the error instead
}

func main() {
    // ------------------------------------------------------------------------
    // Validate a bad struct — every broken rule reports
    // ------------------------------------------------------------------------
    bad := User{Name: "A", Age: -3, Email: "", Role: "wizard"}
    fmt.Println("bad user:")
    for _, p := range Validate(bad) {
        fmt.Println("  \xe2\x9c\x97", p)
    }

    // ------------------------------------------------------------------------
    // A good struct — zero problems
    // ------------------------------------------------------------------------
    good := User{Name: "Ada", Age: 36, Email: "ada@example.com", Role: "admin"}
    if ps := Validate(good); len(ps) == 0 {
        fmt.Println("good user: \xe2\x9c\x93 no problems")
    }

    // ------------------------------------------------------------------------
    // Tag.Lookup — "absent" vs "present but empty"
    // ------------------------------------------------------------------------
    if sf, ok := reflect.TypeOf(User{}).FieldByName("Role"); ok {
        if v, present := sf.Tag.Lookup("validate"); present {
            fmt.Printf("raw tag on Role: %q\n", v) // "oneof=admin|user|guest"
        }
    }

    // ------------------------------------------------------------------------
    // COST & SAFETY NOTES
    // ------------------------------------------------------------------------
    //
    //   * reflection is slow (string parsing + interface boxing):
    //     fine at request/ingest boundaries, not in hot loops
    //   * tags aren't compiler-checked — a typo (`required` ->
    //     `reqired`) fails SILENTLY. Tests like the "bad user" block
    //     above are the safety net.
    //   * with a POINTER input, reflection can also WRITE fields
    //     (field.Set...) — that's exactly how json.Unmarshal fills
    //     structs from JSON.
}
