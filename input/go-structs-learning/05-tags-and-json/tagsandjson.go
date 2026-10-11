// ============================================================================
// EXAMPLE 05 — STRUCT TAGS + JSON
// ============================================================================
//
// A struct tag is a metadata STRING attached to a field. It does
// nothing at compile time — its entire purpose is to be read later
// via reflection by libraries (encoding/json, validator, orm...).
//
// TAG ANATOMY:
//
//     `json:"email,omitempty"`
//       │     │     │
//       │     │     └── options, comma-separated
//       │     └──────── the value for this key
//       └────────────── the tag key (namespace)
//
// Multiple keys are space-separated inside ONE backquoted string:
//     `json:"name" xml:"nombre" validate:"required"`
//
// RULE: tags must be a STRING LITERAL in backquotes — concatenated
// strings or constants do not count.
package main

import (
    "encoding/json"
    "fmt"
    "reflect"
)

type User struct {
    ID        int    `json:"id"`              // rename the JSON key
    Name      string `json:"name"`
    Email     string `json:"email,omitempty"` // drop the key when empty
    Password  string `json:"-"`               // "-" = never (un)marshal
    CreatedAt string `json:"created_at"`      // snake_case convention

    // Unexported fields are NEVER marshaled — encoding/json only
    // touches exported fields, no matter what the tag says.
    secret string
}

func main() {
    // ------------------------------------------------------------------------
    // MARSHAL — struct -> JSON ([]byte of UTF-8 text)
    // ------------------------------------------------------------------------
    u := User{ID: 1, Name: "ada", CreatedAt: "2024-01-15", secret: "x"}
    b, err := json.Marshal(u)
    if err != nil {
        panic(err)
    }
    fmt.Println(string(b))
    // output: {"id":1,"name":"ada","created_at":"2024-01-15"}
    //   * no "email"  -> omitempty dropped the empty string
    //   * no Password -> "-" excluded it entirely
    //   * no secret   -> unexported fields are invisible to json

    // ------------------------------------------------------------------------
    // UNMARSHAL — JSON -> struct (note the & : it must FILL the struct)
    // ------------------------------------------------------------------------
    raw := []byte(`{"id":2,"name":"grace","created_at":"2023-06-01"}`)
    var u2 User
    if err := json.Unmarshal(raw, &u2); err != nil {
        panic(err)
    }
    fmt.Printf("%+v\n", u2)

    // omitempty is a MARSHAL-only option — it has no effect on
    // Unmarshal, which simply leaves absent keys at their zero values.

    // ------------------------------------------------------------------------
    // READING TAGS YOURSELF — this is all reflection ever does
    // ------------------------------------------------------------------------
    //
    // Tag.Get(key)  returns "" when absent (can't distinguish
    //               "no tag" from "empty value")
    // Tag.Lookup    returns (value, present) — use when that
    //               difference matters
    t := reflect.TypeOf(User{})
    fmt.Println("--- tags on User ---")
    for i := 0; i < t.NumField(); i++ {
        f := t.Field(i)
        if tag, ok := f.Tag.Lookup("json"); ok {
            fmt.Printf("  %-10s json=%q\n", f.Name, tag)
        }
    }

    // ------------------------------------------------------------------------
    // KEY POINT
    // ------------------------------------------------------------------------
    // A misspelled tag SILENTLY does nothing — `json:"nme"` just means
    // the field marshals under its Go name. Tags are strings; the
    // compiler cannot check them. Example 16 shows how libraries parse
    // them, which makes such bugs easy to spot.
}
