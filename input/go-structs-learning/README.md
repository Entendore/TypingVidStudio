# Go Structs — Learning Examples

Heavily annotated, runnable examples — each folder is its own `main` package:

    go run ./01-basics

Generated for Go 1.24+.

| Dir | Topic |
|-----|-------|
| 01-basics                | Declaring, creating, accessing structs |
| 02-initialization        | Literals, new(), pointers |
| 03-methods               | Value vs pointer receivers |
| 04-nested-and-embedding  | Composition, embedding, promotion |
| 05-tags-and-json         | Struct tags, JSON marshal/unmarshal |
| 06-comparison-and-copy   | Copy semantics, ==, DeepEqual, map keys |
| 07-anonymous-structs     | Inline types, table-driven tests |
| 08-constructors          | NewXxx pattern, validation, Stringer |
| 09-interfaces            | Method sets: the *T gotcha |
| 10-generics              | Generic structs and constraints |
| 11-mutex-embedding       | Concurrency-safe structs |
| 12-functional-options    | Optional constructor parameters |
| 13-memory-layout         | Alignment, padding, unsafe.Sizeof |
| 14-self-referential      | Linked lists, trees, nil receivers (+tests) |
| 15-interface-embedding   | Decorators and partial mocks |
| 16-custom-tags           | Reflection mini-validator |
| 17-gotchas               | Aliasing, range copies, dangling pointers |
| 18-capstone-kvstore      | Capstone: generic thread-safe KV store (+tests) |

Tips:
    go test ./14-self-referential          # example 14 ships tests
    go run -race ./11-mutex-embedding      # race-detector demo
    go test -race ./18-capstone-kvstore    # capstone, race-checked
Examples build on each other — read top to bottom.
