//! neural_network.zig — idiomatic Zig: a comptime-generic function that
//! returns a type (layer sizes become part of the type), std.Random.Xoshiro,
//! defer for cleanup, @-builtins. Build (Zig 0.12-0.13):
//!   zig build-exe neural_network.zig -O ReleaseFast && ./neural_network
//!
//! HOW IT WORKS
//! ------------
//! Network: n_in -> n_hidden (sigmoid) -> n_out (sigmoid), trained by SGD
//! on mean squared error.
//!
//! FORWARD   hidden[j] = sigmoid(b1[j] + sum_i x[i] * w1[i][j])
//!           out[k]    = sigmoid(b2[k] + sum_j hidden[j] * w2[j][k])
//!           sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)
//!
//! BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
//!           d_out[k]    = (out[k] - y[k]) * out[k] * (1 - out[k])
//!           d_hidden[j] = (sum_k d_out[k] * w2[j][k]) * hidden[j] * (1 - hidden[j])
//!
//! UPDATE    every gradient = delta * activation feeding that edge:
//!           w2[j][k] -= lr * d_out[k] * hidden[j]    b2[k] -= lr * d_out[k]
//!           w1[i][j] -= lr * d_hidden[j] * x[i]      b1[j] -= lr * d_hidden[j]
//!
//! Replace the "toy dataset" block in main() with real data to train on it.

const std = @import("std");

fn sigmoid(x: f64) f64 {
    return 1.0 / (1.0 + @exp(-x));
}

/// Box-Muller standard normal on top of the std Random interface.
fn gauss(rng: std.Random) f64 {
    var u = rng.float(f64);
    while (u == 0.0) u = rng.float(f64);
    const v = rng.float(f64);
    return @sqrt(-2.0 * @log(u)) * @cos(2.0 * std.math.pi * v);
}

/// The classic Zig pattern: a function parameterised at compile time that
/// returns a struct type. n_in/n_hidden/n_out are part of the type itself.
fn Mlp(comptime n_in: usize, comptime n_hidden: usize, comptime n_out: usize) type {
    return struct {
        const Self = @This();

        lr: f64,
        w1: [n_in][n_hidden]f64,
        b1: [n_hidden]f64,
        w2: [n_hidden][n_out]f64,
        b2: [n_out]f64,
        hidden: [n_hidden]f64 = undefined,

        fn init(lr: f64, rng: std.Random) Self {
            var self = Self{
                .lr = lr,
                .w1 = undefined,
                .b1 = [_]f64{0} ** n_hidden,
                .w2 = undefined,
                .b2 = [_]f64{0} ** n_out,
            };
            for (&self.w1) |*row| initRow(row, 2.0 / n_in, rng);
            for (&self.w2) |*row| initRow(row, 2.0 / n_hidden, rng);
            return self;
        }

        fn initRow(row: []f64, inv: f64, rng: std.Random) void {
            for (row) |*w| w.* = gauss(rng) * @sqrt(inv);   // He-style init
        }

        /// Forward pass; caches hidden activations for trainStep.
        fn forward(self: *Self, x: *const [n_in]f64) [n_out]f64 {
            for (0..n_hidden) |j| {
                var z = self.b1[j];
                for (x, 0..) |xi, i| z += xi * self.w1[i][j];
                self.hidden[j] = sigmoid(z);
            }
            var out: [n_out]f64 = undefined;
            for (0..n_out) |k| {
                var z = self.b2[k];
                for (self.hidden, 0..) |h, j| z += h * self.w2[j][k];
                out[k] = sigmoid(z);
            }
            return out;
        }

        /// One SGD step; returns the sample's squared error.
        fn trainStep(self: *Self, x: *const [n_in]f64, y: *const [n_out]f64) f64 {
            const out = self.forward(x);

            var d_out: [n_out]f64 = undefined;
            var sq_err: f64 = 0.0;
            for (0..n_out) |k| {
                const d = out[k] - y[k];
                d_out[k] = d * out[k] * (1.0 - out[k]);   // error * sigmoid'(out)
                sq_err += d * d;
            }

            var d_hidden: [n_hidden]f64 = undefined;
            for (0..n_hidden) |j| {
                var back: f64 = 0.0;
                for (d_out, 0..) |d, k| back += d * self.w2[j][k];
                d_hidden[j] = back * self.hidden[j] * (1.0 - self.hidden[j]);
            }

            for (0..n_hidden) |j| {
                for (0..n_out) |k| self.w2[j][k] -= self.lr * d_out[k] * self.hidden[j];
            }
            for (0..n_out) |k| self.b2[k] -= self.lr * d_out[k];
            for (0..n_in) |i| {
                for (0..n_hidden) |j| self.w1[i][j] -= self.lr * d_hidden[j] * x[i];
            }
            for (0..n_hidden) |j| self.b1[j] -= self.lr * d_hidden[j];
            return sq_err;
        }
    };
}

pub fn main() !void {
    // The one mandatory Zig idiom: an explicit allocator, released via defer.
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    const n_in = 4;
    const n_hidden = 8;
    const n_out = 2;
    const lr = 0.5;
    const epochs = 1000;

    var prng = std.Random.Xoshiro.init(42);
    const rng = prng.random();

    var net = Mlp(n_in, n_hidden, n_out).init(lr, rng);

    // Toy dataset — replace with your own.
    const Sample = struct { x: [n_in]f64, y: [n_out]f64 };
    var data_prng = std.Random.Xoshiro.init(7);
    const data = data_prng.random();

    const dataset = try allocator.alloc(Sample, 64);
    defer allocator.free(dataset);
    for (dataset) |*s| {
        for (&s.x) |*v| v.* = data.float(f64);
        for (&s.y) |*v| v.* = data.float(f64);
    }

    const show_every = @max(epochs / 10, 1);
    const stdout = std.io.getStdOut().writer();
    var epoch: usize = 1;
    while (epoch <= epochs) : (epoch += 1) {
        var loss: f64 = 0.0;
        for (dataset) |s| loss += net.trainStep(&s.x, &s.y);
        if (epoch % show_every == 0) {
            try stdout.print("epoch {d:5}  mse = {d:.6}\n", .{ epoch, loss / dataset.len });
        }
    }
}
