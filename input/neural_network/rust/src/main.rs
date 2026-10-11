//! Idiomatic Rust: iterator pipelines over flat row-major storage, doc
//! comments, inline format args, and unit tests. No external crates.
//! Run: cargo run --release
//!
//! HOW IT WORKS
//! ------------
//! Network: n_in -> n_hidden (sigmoid) -> n_out (sigmoid), trained by SGD
//! on mean squared error.
//!
//! FORWARD   hidden[j] = sigmoid(b1[j] + sum_i x[i] * w1[i*n_hidden + j])
//!           out[k]    = sigmoid(b2[k] + sum_j hidden[j] * w2[j*n_out + k])
//!           sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)
//!
//! BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
//!           d_out[k]    = (out[k] - y[k]) * out[k] * (1 - out[k])
//!           d_hidden[j] = (sum_k d_out[k] * w2[j*n_out+k]) * h[j] * (1 - h[j])
//!
//! UPDATE    every gradient = delta * activation feeding that edge:
//!           w2[j][k] -= lr * d_out[k] * hidden[j]    b2[k] -= lr * d_out[k]
//!           w1[i][j] -= lr * d_hidden[j] * x[i]      b1[j] -= lr * d_hidden[j]
//!
//! Replace the "toy dataset" block in main() with real data to train on it.

#![forbid(unsafe_code)]

use std::f64::consts::PI;

/// Deterministic SplitMix64 PRNG (keeps the crate dependency-free).
struct Rng {
    state: u64,
}

impl Rng {
    fn new(seed: u64) -> Self {
        Self { state: seed }
    }

    /// Next uniform in [0, 1).
    fn uniform(&mut self) -> f64 {
        self.state = self
            .state
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        (self.state >> 11) as f64 / (1u64 << 53) as f64
    }

    /// Standard-normal draw via Box-Muller.
    fn normal(&mut self) -> f64 {
        let u = self.uniform().max(1e-12);
        (-2.0 * u.ln()).sqrt() * (2.0 * PI * self.uniform()).cos()
    }
}

fn sigmoid(x: f64) -> f64 {
    1.0 / (1.0 + (-x).exp())
}

/// v . w[offset], w[offset + stride], w[offset + 2*stride], ...
/// i.e. a dot product with one column of a row-major matrix.
fn dot_column(v: &[f64], w: &[f64], stride: usize) -> f64 {
    v.iter()
        .zip(w.iter().step_by(stride))
        .map(|(x, w)| x * w)
        .sum()
}

/// One-hidden-layer MLP with sigmoid activations, trained by SGD.
#[derive(Debug, Clone)]
struct NeuralNetwork {
    lr: f64,
    n_in: usize,
    n_hidden: usize,
    n_out: usize,
    /// Row-major [n_in x n_hidden].
    w1: Vec<f64>,
    b1: Vec<f64>,
    /// Row-major [n_hidden x n_out].
    w2: Vec<f64>,
    b2: Vec<f64>,
    /// Hidden activations cached by the last [`forward`].
    hidden: Vec<f64>,
}

impl NeuralNetwork {
    fn new(n_in: usize, n_hidden: usize, n_out: usize, lr: f64, seed: u64) -> Self {
        let mut rng = Rng::new(seed);
        let he = |rows: usize, cols: usize| {
            let scale = (2.0 / rows as f64).sqrt();
            std::iter::repeat_with(|| rng.normal() * scale)
                .take(rows * cols)
                .collect::<Vec<f64>>()
        };
        Self {
            lr,
            n_in,
            n_hidden,
            n_out,
            w1: he(n_in, n_hidden),
            b1: vec![0.0; n_hidden],
            w2: he(n_hidden, n_out),
            b2: vec![0.0; n_out],
            hidden: vec![0.0; n_hidden],
        }
    }

    /// Forward pass for one sample; caches hidden activations for `train_step`.
    fn forward(&mut self, x: &[f64]) -> Vec<f64> {
        for (j, h) in self.hidden.iter_mut().enumerate() {
            *h = sigmoid(self.b1[j] + dot_column(x, &self.w1[j..], self.n_hidden));
        }
        (0..self.n_out)
            .map(|k| sigmoid(self.b2[k] + dot_column(&self.hidden, &self.w2[k..], self.n_out)))
            .collect()
    }

    /// One SGD step for a sample; returns the sample's squared error.
    fn train_step(&mut self, x: &[f64], y: &[f64]) -> f64 {
        let out = self.forward(x);

        let d_out: Vec<f64> = out
            .iter()
            .zip(y)
            .map(|(o, t)| (o - t) * o * (1.0 - o))       // error * sigmoid'(out)
            .collect();
        let sq_err: f64 = out.iter().zip(y).map(|(o, t)| (o - t) * (o - t)).sum();

        let d_hidden: Vec<f64> = (0..self.n_hidden)
            .map(|j| {
                let back = dot_column(&d_out, &self.w2[j..], self.n_out);
                back * self.hidden[j] * (1.0 - self.hidden[j])  // * sigmoid'(h)
            })
            .collect();

        // w2 -= lr * d_out (outer) hidden — rank-1 update per row.
        for (j, &h) in self.hidden.iter().enumerate() {
            let row = &mut self.w2[j * self.n_out..(j + 1) * self.n_out];
            for (k, w) in row.iter_mut().enumerate() {
                *w -= self.lr * d_out[k] * h;
            }
        }
        for (b, d) in self.b2.iter_mut().zip(&d_out) {
            *b -= self.lr * d;
        }
        for (i, &xi) in x.iter().enumerate() {
            for (j, &d) in d_hidden.iter().enumerate() {
                self.w1[i * self.n_hidden + j] -= self.lr * d * xi;
            }
        }
        for (b, d) in self.b1.iter_mut().zip(&d_hidden) {
            *b -= self.lr * d;
        }
        sq_err
    }
}

fn main() {
    let n_in: usize = 4;
    let n_hidden: usize = 8;
    let n_out: usize = 2;
    let lr: f64 = 0.5;
    let epochs: usize = 1000;

    let mut net = NeuralNetwork::new(n_in, n_hidden, n_out, lr, 42);

    // Toy dataset — replace with your own.
    let mut data = Rng::new(7);
    let dataset: Vec<(Vec<f64>, Vec<f64>)> = std::iter::repeat_with(|| {
        (
            std::iter::repeat_with(|| data.uniform()).take(n_in).collect(),
            std::iter::repeat_with(|| data.uniform()).take(n_out).collect(),
        )
    })
    .take(64)
    .collect();

    let show_every = (epochs / 10).max(1);
    for epoch in 1..=epochs {
        let loss: f64 = dataset.iter().map(|(x, y)| net.train_step(x, y)).sum();
        if epoch % show_every == 0 {
            println!("epoch {epoch:5}  mse = {loss:.6}");
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sigmoid_at_zero_is_one_half() {
        assert!((sigmoid(0.0) - 0.5).abs() < 1e-12);
    }

    #[test]
    fn training_reduces_error_on_a_single_sample() {
        let mut net = NeuralNetwork::new(1, 4, 1, 0.9, 7);
        let (x, y) = ([0.8], [1.0]);
        let err = |net: &mut NeuralNetwork| (net.forward(&x)[0] - y[0]).powi(2);
        let before = err(&mut net);
        for _ in 0..50 {
            net.train_step(&x, &y);
        }
        assert!(err(&mut net) < before, "loss should decrease");
    }
}
