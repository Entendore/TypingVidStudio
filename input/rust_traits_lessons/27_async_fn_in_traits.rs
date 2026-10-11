// ============================================================================
// LESSON 27 - async fn in Traits (RPITIT) + async dyn Dispatch
// ============================================================================
// Requires Rust 1.75+ (native async fn in traits).
// Self-contained: includes a ~20-line TOY executor so the file runs with
// plain rustc - no tokio needed. Focus on the traits; the executor is setup.
//
// Run me:  rustc --edition 2021 27_async_fn_in_traits.rs && ./27_async_fn_in_traits
// ============================================================================

use std::future::Future;
use std::pin::Pin;
use std::sync::Arc;
use std::task::{Context, Poll, Wake, Waker};
use std::thread;
use std::time::Duration;

// === TOY EXECUTOR (not the lesson) =========================================
struct SpinWake;
impl Wake for SpinWake {
    fn wake(self: Arc<Self>) {} // our futures never really park
}

// block_on: drive a future to completion on this thread.
fn block_on<F: Future>(fut: F) -> F::Output {
    let mut fut = Box::pin(fut);
    let waker = Waker::from(Arc::new(SpinWake));
    let mut cx = Context::from_waker(&waker);
    loop {
        match fut.as_mut().poll(&mut cx) {
            Poll::Ready(out) => return out,
            Poll::Pending => thread::yield_now(), // toy: busy-wait politely
        }
    }
}

// A future that sleeps once, then completes. (Real runtimes use timers +
// wakers; this is honest enough for a demo.)
struct Delay {
    ms: u64,
    fired: bool,
}

impl Future for Delay {
    type Output = ();
    fn poll(mut self: Pin<&mut Self>, _: &mut Context<'_>) -> Poll<()> {
        if self.fired {
            return Poll::Ready(());
        }
        thread::sleep(Duration::from_millis(self.ms));
        self.fired = true;
        Poll::Ready(())
    }
}

// === THE LESSON ============================================================

// 1. NATIVE async fn IN A TRAIT (stable 1.75):
trait Fetch {
    async fn fetch(&self, url: &str) -> String;
}
// Desugars to RPITIT - "return-position impl Trait in trait":
//     fn fetch(&self, url: &str) -> impl Future<Output = String>;
// The future borrows &self, so the borrow checker keeps it honest.

struct Cache;
struct Network;

impl Fetch for Cache {
    async fn fetch(&self, _url: &str) -> String {
        Delay { ms: 10, fired: false }.await;
        "payload from cache".into()
    }
}

impl Fetch for Network {
    async fn fetch(&self, url: &str) -> String {
        Delay { ms: 40, fired: false }.await;
        format!("payload from {} over the network", url)
    }
}

// 2. EXPLICIT FORM - promise the future is `Send` so runtimes may spawn it
//    on another thread. With `async fn` sugar you can't say this, so drop
//    to the RPITIT form when you need it:
trait FetchSend {
    fn fetch(&self, url: &str) -> impl Future<Output = String> + Send;
}

struct StrictFetcher;

impl FetchSend for StrictFetcher {
    fn fetch(&self, url: &str) -> impl Future<Output = String> + Send {
        async move { format!("{} (Send future)", url) } // captures nothing
    }
}

// 3. DYN DISPATCH OF ASYNC METHODS.
// `dyn Fetch` does NOT compile: async methods make a trait NOT
// dyn-compatible (E0038) - the returned future's type depends on Self, and
// one vtable slot can't hold infinitely many future types.
//
//     let objs: Vec<Box<dyn Fetch>> = ...;   // ERROR
//
// The fix (exactly what the `async-trait` crate generates for you):
// return a boxed dyn Future instead of an anonymous one. That IS a single
// named type, so the trait becomes dyn-compatible again.
trait FetchDyn {
    fn fetch(&self, url: &str) -> Pin<Box<dyn Future<Output = String> + '_>>;
    //                                                        ^^ borrows self
}

impl FetchDyn for Cache {
    fn fetch(&self, _url: &str) -> Pin<Box<dyn Future<Output = String> + '_>> {
        Box::pin(async {
            Delay { ms: 10, fired: false }.await;
            "payload from cache".into()
        })
    }
}

impl FetchDyn for Network {
    fn fetch(&self, url: &str) -> Pin<Box<dyn Future<Output = String> + '_>> {
        Box::pin(async move {
            Delay { ms: 40, fired: false }.await;
            format!("payload from {} over the network", url)
        })
    }
}

fn main() {
    // Static dispatch: one specialized future per implementor (lesson 03).
    let cache = Cache;
    let net = Network;
    println!("{}", block_on(cache.fetch("rust-lang.org")));
    println!("{}", block_on(net.fetch("rust-lang.org")));
    println!("{}", block_on(StrictFetcher.fetch("rust-lang.org")));

    // Dynamic dispatch: MIXED implementors behind one trait object
    // (lesson 05) - now with async methods.
    let sources: Vec<Box<dyn FetchDyn>> = vec![Box::new(Cache), Box::new(Network)];
    for s in &sources {
        println!("dyn: {}", block_on(s.fetch("example.com")));
    }

    // DECISION GUIDE
    //   app code, one runtime known     -> native async fn in traits (zero cost)
    //   need dyn / plugin-style mocking -> boxed-future methods or async-trait
    //   designing a public library API  -> decide dyn-compatibility UP FRONT;
    //                                      you can't retrofit it later!
}
