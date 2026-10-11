// Tests for example 14 — recursive structures are ideal test
// subjects: small, pure, easy to build from literals.
//
//   go test ./14-self-referential
//   go test -v ./14-self-referential    # see subtests
package main

import "testing"

// ----------------------------------------------------------------------------
// t.Helper() marks a function as a test helper: failures inside it
// are reported at the CALLER's line, not in the helper.
// ----------------------------------------------------------------------------
func buildList(vals ...int) *Node {
    var n *Node
    for _, v := range vals {
        n = n.Push(v)
    }
    return n
}

func TestList(t *testing.T) {
    // Nil receiver calls are a designed-in feature — test it:
    var empty *Node
    if empty.Len() != 0 {
        t.Fatal("empty list should have len 0")
    }

    list := buildList(3, 2, 1) // head is the LAST pushed: 1
    if list.Len() != 3 {
        t.Fatalf("len = %d, want 3", list.Len())
    }
    if list.Value != 1 {
        t.Fatalf("head = %d, want 1 (last pushed)", list.Value)
    }
}

func TestTree(t *testing.T) {
    var tree *Tree
    for _, v := range []int{5, 3, 7, 1} {
        tree = tree.Insert(v)
    }

    if !tree.Search(7) || tree.Search(99) {
        t.Fatal("Search is broken")
    }

    // The BST invariant implies in-order == sorted:
    got := []int{}
    tree.InOrder(func(v int) { got = append(got, v) })
    want := []int{1, 3, 5, 7}
    for i := range want {
        if got[i] != want[i] {
            t.Fatalf("in-order = %v, want %v", got, want)
        }
    }
}

// Table-driven tests with an ANONYMOUS struct (example 07) — the
// idiomatic shape for "same operation, many cases":
func TestTreeTable(t *testing.T) {
    tests := []struct {
        name   string
        vals   []int
        search int
        found  bool
    }{
        {"single", []int{5}, 5, true},
        {"miss", []int{1, 2, 3}, 99, false},
        {"empty tree", nil, 1, false},
    }
    for _, tc := range tests {
        t.Run(tc.name, func(t *testing.T) {
            var tree *Tree
            for _, v := range tc.vals {
                tree = tree.Insert(v)
            }
            if got := tree.Search(tc.search); got != tc.found {
                t.Fatalf("Search(%d) = %v, want %v", tc.search, got, tc.found)
            }
        })
    }
}
