# Rust Traits - Learning Playground

Every `NN_*.rs` file is a standalone, compilable program with heavy
learning comments. `exercises/` contains deliberately broken code for
you to fix; `solutions/` has the corrected versions.

## Version requirements

| Feature | Lesson | Rust |
|---------|--------|------|
| GATs | 21 | 1.65+ |
| async fn in traits (RPITIT) | 27 | 1.75+ |
| trait upcasting | 28, 33 | 1.86+ |

## Run a lesson

    rustc --edition 2021 01_trait_basics.rs && ./01_trait_basics

## Run all lessons (top-level only; exercises stay out of the way)

    for f in *.rs; do rustc --edition 2021 "$f" && ./"${f%.rs}"; done

## Run lesson 25's tests

    rustc --edition 2021 --test 25_testing_with_traits.rs && ./25_testing_with_traits

## Workbook

Work in `exercises/`: read the expected error in each file's header, run
it, fix it, then diff against `solutions/`.

    cd exercises && rustc --edition 2021 ex01_hello_trait.rs && ./ex01_hello_trait

| Exercise | Skill | Solution fix |
|----------|-------|--------------|
| ex01 | write your first impl block | E0599 -> implement Greeter |
| ex02 | satisfy a trait bound | E0277 -> #[derive(Debug)] |
| ex03 | make a trait dyn-compatible | E0038 -> &dyn parameter |
| ex04 | implement Iterator | todo!() -> next() contract |
| ex05 | escape the orphan rule | E0117 -> newtype pattern |

## Lessons

| File | Topic |
|------|-------|
| 01 | Trait basics: define, implement, call |
| 02 | Default implementations & overriding |
| 03 | Traits as parameters (`impl Trait`, bounds, `where`) |
| 04 | Returning `impl Trait` (and its limitation) |
| 05 | Trait objects (`dyn`) & dynamic dispatch |
| 06 | Common std traits: Display, Debug, Clone, Drop |
| 07 | Operator overloading via traits |
| 08 | Associated types |
| 09 | Supertraits, deriving, marker traits, orphan rule |
| 10 | Blanket implementations & conditional impls |
| 11 | Implementing Iterator (get 70 adapters free) |
| 12 | From / Into / TryFrom conversions |
| 13 | Deref & DerefMut, deref coercion |
| 14 | Extension traits (adding methods to foreign types) |
| 15 | Name clashes & fully qualified syntax `<T as Trait>::m()` |
| 16 | Dyn compatibility (object safety), `where Self: Sized` |
| 17 | CAPSTONE 1: media library |
| 18 | Closures are traits: Fn, FnMut, FnOnce |
| 19 | Sized, ?Sized, unsized types & fat pointers |
| 20 | AsRef & Borrow: flexible parameter traits |
| 21 | Lifetimes in traits & GATs (lending iterators) |
| 22 | Sealed traits: controlling who can implement |
| 23 | Send & Sync: concurrency safety as traits |
| 24 | The newtype pattern |
| 25 | Testing with traits: DI, spies, `rustc --test` |
| 26 | CAPSTONE 2: undo/redo editor |
| 27 | async fn in traits (RPITIT) + boxed-future dyn dispatch (1.75+) |
| 28 | Trait upcasting: dyn Sub -> dyn Super (1.86+) |
| 29 | Const generics + traits ([(); N - 1] guard, associated consts) |
| 30-32 | (reserved - workbook occupies exercises/ folder) |
| 33 | CAPSTONE 3: CI pipeline runner (upcasting + closures + retries) |

## Cheat sheet

    trait Speak { fn speak(&self) -> String; }    // define
    impl Speak for Dog { ... }                    // implement
    fn f(x: &impl Speak)                          // accept any implementor
    fn f<T: Speak>(x: &T)                         // same, generic form
    fn f() -> impl Speak                          // return some implementor
    Vec<Box<dyn Speak>>                           // mixed types, runtime dispatch
    #[derive(Debug, Clone, PartialEq)]            // auto-implement common traits
    impl<T: Display> Mine for T { }               // blanket impl
    impl From<A> for B { }                        // B::from(a) + a.into()
    impl Iterator for C { type Item = T; fn next(&mut self) -> Option<T>; }
    <Dog as Animal>::baby_name()                  // disambiguation
    fn m(&self) -> Self where Self: Sized;        // keep method out of dyn
    F: FnOnce | FnMut | Fn                        // closure traits (Fn: FnMut: FnOnce)
    fn f<T: Debug + ?Sized>(x: &T)                // accept unsized behind a ref
    fn f<A: AsRef<str>>(a: A)                     // flexible string-ish params
    trait T { type Item<'a> where Self: 'a; }     // GAT (1.65+)
    trait T: private::Sealed {}                   // sealed trait pattern
    T: Send / T: Sync                             // thread safety markers
    struct Meters(f64);                           // newtype: orphan fix + unit safety
    trait T { async fn f(&self) -> R; }           // = -> impl Future (1.75+)
    fn f(&self) -> Pin<Box<dyn Future<Out> + '_>> // dyn-compatible async method
    let a: &dyn Animal = &dog_obj;                // upcast dyn Sub->Super (1.86+)
    impl<const N: usize> T for [u8; N] {}         // const-generic impl
    where [(); N - 1]:                            // require N >= 1
    trait C { const MAX: usize; }                 // associated const
