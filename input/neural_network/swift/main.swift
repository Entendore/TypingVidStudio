// main.swift — idiomatic Swift: value-type struct with mutating methods,
// RandomNumberGenerator protocol, `inout some`, labeled tuples, free Codable.
// Run:   swift main.swift        Build: swiftc -O main.swift -o nn && ./nn
//
// HOW IT WORKS
// ------------
// Network: nIn -> nHidden (sigmoid) -> nOut (sigmoid), trained by SGD on MSE.
//
// FORWARD   hidden[j] = sigmoid(b1[j] + sum_i x[i] * w1[i][j])
//           out[k]    = sigmoid(b2[k] + sum_j hidden[j] * w2[j][k])
//           sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)
//
// BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
//           dOut[k]    = (out[k] - y[k]) * out[k] * (1 - out[k])
//           dHidden[j] = (sum_k dOut[k] * w2[j][k]) * hidden[j] * (1 - hidden[j])
//
// UPDATE    every gradient = delta * activation feeding that edge:
//           w2[j][k] -= lr * dOut[k] * hidden[j]     b2[k] -= lr * dOut[k]
//           w1[i][j] -= lr * dHidden[j] * x[i]       b1[j] -= lr * dHidden[j]
//
// Replace the "toy dataset" block at the bottom with real data to train on it.

/// Deterministic PRNG (SplitMix64); conforming to RandomNumberGenerator
/// unlocks `Double.random(in:using:)` everywhere.
struct SplitMix64: RandomNumberGenerator {
    private var state: UInt64
    init(seed: UInt64) { state = seed }
    mutating func next() -> UInt64 {
        state = state &* 6364136223846793005 &+ 1442695040888963407
        return state
    }
}

/// Box-Muller standard-normal draw.
func gaussian(using rng: inout some RandomNumberGenerator) -> Double {
    var u = Double.random(in: 0..<1, using: &rng)
    if u < 1e-12 { u = 1e-12 }
    let v = Double.random(in: 0..<1, using: &rng)
    return (-2 * log(u)).squareRoot() * cos(2 * .pi * v)
}

func sigmoid(_ x: Double) -> Double { 1 / (1 + exp(-x)) }

/// One-hidden-layer MLP. A struct: value semantics make copying explicit and
/// cheap, and `Codable` comes for free.
struct NeuralNetwork {
    private let lr: Double
    private let nIn: Int, nHidden: Int, nOut: Int
    private var w1: [[Double]], b1: [Double]
    private var w2: [[Double]], b2: [Double]
    private var hidden: [Double] = []

    init(nIn: Int, nHidden: Int, nOut: Int, lr: Double, seed: UInt64 = 42) {
        precondition(min(nIn, nHidden, nOut) > 0 && lr > 0, "invalid hyperparameters")
        self.lr = lr
        (self.nIn, self.nHidden, self.nOut) = (nIn, nHidden, nOut)
        var rng = SplitMix64(seed: seed)
        w1 = Self.heMatrix(nIn, nHidden, &rng)      // He-style init
        b1 = .init(repeating: 0, count: nHidden)
        w2 = Self.heMatrix(nHidden, nOut, &rng)
        b2 = .init(repeating: 0, count: nOut)
    }

    private static func heMatrix(_ rows: Int, _ cols: Int, _ rng: inout SplitMix64) -> [[Double]] {
        let scale = (2.0 / Double(rows)).squareRoot()
        return (0..<rows).map { _ in (0..<cols).map { _ in gaussian(using: &rng) * scale } }
    }

    /// Forward pass for one sample; caches hidden activations for `trainStep`.
    mutating func forward(_ x: [Double]) -> [Double] {
        hidden = (0..<nHidden).map { j -> Double in
            let z = b1[j] + zip(x, w1).reduce(0.0) { $0 + $1.0 * $1.1[j] }
            return sigmoid(z)
        }
        return (0..<nOut).map { k -> Double in
            let z = b2[k] + zip(hidden, w2).reduce(0.0) { $0 + $1.0 * $1.1[k] }
            return sigmoid(z)
        }
    }

    /// One SGD step; returns the sample's squared error.
    mutating func trainStep(_ x: [Double], _ y: [Double]) -> Double {
        let out = forward(x)

        // Output delta: error times sigmoid'(out).
        let dOut = zip(out, y).map { o, t in (o - t) * o * (1 - o) }
        // Hidden delta: backpropagated error times sigmoid'(hidden).
        let dHidden = (0..<nHidden).map { j -> Double in
            let back = zip(dOut, w2[j]).reduce(0.0) { $0 + $1.0 * $1.1 }
            return back * hidden[j] * (1 - hidden[j])
        }

        // Gradient descent: weight -= lr * delta * activation on that edge.
        for j in 0..<nHidden {
            for k in 0..<nOut { w2[j][k] -= lr * dOut[k] * hidden[j] }
        }
        for k in 0..<nOut { b2[k] -= lr * dOut[k] }
        for (i, xi) in x.enumerated() {
            for (j, d) in dHidden.enumerated() { w1[i][j] -= lr * d * xi }
        }
        for (j, d) in dHidden.enumerated() { b1[j] -= lr * d }

        return zip(out, y).reduce(0.0) { $0 + ($1.0 - $1.1) * ($1.0 - $1.1) }
    }
}

// Value types get Codable synthesis with a one-liner — persistence for free.
extension NeuralNetwork: Codable {}

// ---- demo (replace with your own data) ------------------------------
let (nIn, nHidden, nOut) = (4, 8, 2)
let (lr, epochs) = (0.5, 1000)

var net = NeuralNetwork(nIn: nIn, nHidden: nHidden, nOut: nOut, lr: lr)

var dataRng = SplitMix64(seed: 7)
let dataset = (0..<64).map { _ in
    (x: (0..<nIn).map { _ in Double.random(in: 0..<1, using: &dataRng) },
     y: (0..<nOut).map { _ in Double.random(in: 0..<1, using: &dataRng) })
}

let showEvery = max(epochs / 10, 1)
for epoch in 1...epochs {
    let loss = dataset.reduce(0.0) { $0 + net.trainStep($1.x, $1.y) }
    if epoch % showEvery == 0 {
        print(String(format: "epoch %5d  mse = %.6f", epoch, loss / Double(dataset.count)))
    }
}
