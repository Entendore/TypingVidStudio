// ============================================================================
// EXAMPLE 04 — NESTED STRUCTS vs EMBEDDING (PROMOTION)
// ============================================================================
//
// Two ways to put a struct inside another struct:
//
//   1. NAMED field   Home Address   -> access via p.Home.City
//   2. EMBEDDED field Address       -> Address's fields AND methods
//                                      are "PROMOTED" up: e.City works
//
// EMBEDDING IS NOT INHERITANCE:
//
//   * there is no "is-a" relationship — an Employee is not an Address
//   * the embedded value is a plain FIELD with the TYPE as its name
//   * promotion is pure compiler shorthand: e.City is sugar for
//     e.Address.City
//
package main

import "fmt"

type Address struct {
    City    string
    Country string
}

// Describe will be PROMOTED to any struct that embeds Address.
func (a Address) Describe() string {
    return a.City + ", " + a.Country
}

type Person struct {
    Name string
    Age  int
    Home Address // NAMED: access goes THROUGH the field name
}

type Employee struct {
    Person  Person  // EMBEDDED: no field name — the type IS the name
    Company string  // ordinary field mixed in between embeds
    Address         // EMBEDDED directly
}

func main() {
    // ------------------------------------------------------------------------
    // NAMED composition — explicit, verbose, impossible to confuse
    // ------------------------------------------------------------------------
    p := Person{
        Name: "Grace",
        Age:  29,
        Home: Address{City: "London", Country: "UK"},
    }
    fmt.Println(p.Home.City)       // must name the path
    fmt.Println(p.Home.Describe()) // methods too: p.Home.Describe()

    // ------------------------------------------------------------------------
    // EMBEDDING — the inner type's members are PROMOTED
    // ------------------------------------------------------------------------
    e := Employee{
        Person:  Person{Name: "Alan", Age: 41},
        Company: "Acme",
        Address: Address{City: "Cambridge", Country: "UK"},
    }

    // Promoted FIELDS — both forms refer to the same memory:
    fmt.Println(e.Name, "==", e.Person.Name) // promotion sugar

    // Promoted METHODS — Address.Describe callable on Employee:
    fmt.Println(e.Describe()) // really e.Address.Describe()

    // In the composite LITERAL, embeds are still plain fields keyed
    // by their type name:
    _ = Employee{Person: Person{Name: "x"}, Address: Address{City: "y"}}

    // ------------------------------------------------------------------------
    // PROMOTION RULES the compiler enforces
    // ------------------------------------------------------------------------
    //
    //   * promotion goes one level deep for ambiguity purposes: if
    //     BOTH embedded types had a City field, e.City would not
    //     compile — you must write e.Person.City or e.Address.City
    //
    //   * an OUTER field SHADOWS a promoted one: if Employee had its
    //     own Name field, e.Name would pick Employee's, and e.Person.Name
    //     would still reach the embedded copy — no override, both exist
    //
    //   * promotion works through any depth (e.A.B.C chains), but
    //     deep chains are a design smell — keep it shallow
}
