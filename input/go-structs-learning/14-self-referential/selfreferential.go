// ============================================================================
// EXAMPLE 14 — SELF-REFERENTIAL STRUCTS: LINKED LISTS & TREES
// ============================================================================
//
// A struct may contain a POINTER to its own type — the foundation of
// every linked structure (lists, trees, graphs, tries):
//
//     type Node struct {
//         Next *Node   // LEGAL   — a pointer is one machine word,
//                      //            so its size is known at compile time
//         Next Node    // ILLEGAL — Node inside Node is infinite size;
//                      //            compile error: "invalid recursive type"
//     }
//
// The empty collection is simply NIL — no sentinel nodes needed:
//
//     head: nil                          empty list
//     head: [25|•]→[16|•]→[9|nil]        3-node list
//
package main

import "fmt"

// ----------------------------------------------------------------------------
// SINGLY LINKED LIST
// ----------------------------------------------------------------------------

type Node struct {
    Value int
    Next  *Node // link to the rest of the list; nil terminates it
}

// Push prepends a value and returns the NEW head — O(1), no
// traversals, no special case for the empty list:
//
//     nil.Push(3)         ->  [3|nil]
//     [3|nil].Push(2)     ->  [2|•]→[3|nil]
//
// Returning the new head (instead of mutating) is what makes the
// empty-list case free.
func (n *Node) Push(v int) *Node {
    return &Node{Value: v, Next: n}
}

// KEY POINT — methods on NIL receivers are legal:
//
// A method is just a function with a receiver parameter. Calling one
// on nil is fine AS LONG AS the body never dereferences the receiver.
// Here the loop condition (x != nil) runs first, so this returns 0
// for an empty list instead of panicking.
func (n *Node) Len() int {
    c := 0
    for x := n; x != nil; x = x.Next {
        c++
    }
    return c
}

// ----------------------------------------------------------------------------
// BINARY SEARCH TREE — TWO self-references = branching
// ----------------------------------------------------------------------------

type Tree struct {
    Value       int
    Left, Right *Tree // invariant: Left < Value <= Right
}

// Insert maintains the BST invariant. THE NIL-RECEIVER TRICK:
//
// Calling a method on a nil *Tree is legal if we check for nil FIRST —
// which lets callers write the beautiful recursive one-liner:
//
//     tree = tree.Insert(v)     // works even when tree is nil!
//
// On the very first insert, t is nil, we allocate the root, and
// return it. Every call reassigns the (possibly new) subtree root.
func (t *Tree) Insert(v int) *Tree {
    if t == nil {
        return &Tree{Value: v} // found the empty spot -> put it here
    }
    if v < t.Value {
        t.Left = t.Left.Insert(v)
    } else {
        t.Right = t.Right.Insert(v)
    }
    return t
}

// Search follows the invariant down: O(log n) if the tree is balanced.
func (t *Tree) Search(v int) bool {
    if t == nil {
        return false // walked off the tree — not present
    }
    switch {
    case v < t.Value:
        return t.Left.Search(v)
    case v > t.Value:
        return t.Right.Search(v)
    default:
        return true
    }
}

// InOrder visits left subtree, node, right subtree — which yields
// SORTED order for a BST. The callback keeps this function generic
// (printing, collecting, summing — all without duplicating traversal).
func (t *Tree) InOrder(fn func(int)) {
    if t == nil {
        return
    }
    t.Left.InOrder(fn)
    fn(t.Value)
    t.Right.InOrder(fn)
}

func main() {
    // ------------------------------------------------------------------------
    // Build a list: nil IS the empty list — no special first-push case
    // ------------------------------------------------------------------------
    var list *Node
    for i := 1; i <= 5; i++ {
        list = list.Push(i * i) // 25 -> 16 -> 9 -> 4 -> 1
    }
    for x := list; x != nil; x = x.Next {
        fmt.Printf("%d -> ", x.Value)
    }
    fmt.Println("nil | len:", list.Len()) // len: 5

    // Nil receiver in action — no panic:
    var empty *Node
    fmt.Println("empty len:", empty.Len()) // 0

    // ------------------------------------------------------------------------
    // Build a tree, then reap the benefits of the invariant
    // ------------------------------------------------------------------------
    var tree *Tree // nil — the empty tree
    for _, v := range []int{50, 30, 70, 20, 40, 60, 80} {
        tree = tree.Insert(v)
    }

    sorted := []int{}
    tree.InOrder(func(v int) { sorted = append(sorted, v) })
    fmt.Println("in-order:", sorted) // [20 30 40 50 60 70 80] — sorted!

    fmt.Println("search 40:", tree.Search(40)) // true
    fmt.Println("search 99:", tree.Search(99)) // false
}
