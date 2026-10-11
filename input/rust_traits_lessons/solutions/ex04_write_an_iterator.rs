// SOLUTION 4 - implementing Iterator by hand (lesson 11)
// The contract: each call yields Some(next value) until exhausted, then
// None on every subsequent call. `for` loops keep calling until None.

struct Countdown {
    remaining: u32,
}

impl Iterator for Countdown {
    type Item = u32;

    fn next(&mut self) -> Option<u32> {
        if self.remaining == 0 {
            return None; // exhausted - and stays exhausted
        }
        let value = self.remaining; // capture the value BEFORE stepping
        self.remaining -= 1;
        Some(value)
    }
}

fn main() {
    for n in Countdown { remaining: 3 } {
        print!("{} ", n);
    }
    println!();

    // BONUS - the payoff of implementing ONE method (lesson 11):
    let first_two: Vec<u32> = Countdown { remaining: 5 }.take(2).collect();
    let sum: u32 = Countdown { remaining: 10 }.sum();
    let has_seven = Countdown { remaining: 20 }.any(|n| n == 7);
    println!("take(2) = {:?}, sum = {}, has 7 = {}", first_two, sum, has_seven);
}
