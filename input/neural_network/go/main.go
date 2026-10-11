// main.go — idiomatic Go: math/rand/v2 with PCG (no global seeding), doc
// comments, local value types, builtin max.
// Run: go run main.go   (Go 1.22+)
//
// HOW IT WORKS
// ------------
// Network: n_in -> n_hidden (sigmoid) -> n_out (sigmoid), trained by SGD
// on mean squared error.
//
// FORWARD   hidden[j] = sigmoid(b1[j] + sum_i x[i] * W1[i][j])
//           out[k]    = sigmoid(b2[k] + sum_j hidden[j] * W2[j][k])
//           sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)
//
// BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
//           dOut[k]    = (out[k] - y[k]) * out[k] * (1 - out[k])
//           dHidden[j] = (sum_k dOut[k] * W2[j][k]) * hidden[j] * (1 - hidden[j])
//
// UPDATE    every gradient = delta * activation feeding that edge:
//           W2[j][k] -= lr * dOut[k] * hidden[j]     b2[k] -= lr * dOut[k]
//           W1[i][j] -= lr * dHidden[j] * x[i]       b1[j] -= lr * dHidden[j]
//
// Replace the "toy dataset" block in main() with real data to train on it.
package main

import (
    "fmt"
    "math"
    "math/rand/v2"
)

// MLP is a one-hidden-layer network with sigmoid activations.
type MLP struct {
    lr              float64
    nIn, nHid, nOut int
    w1, w2          [][]float64
    b1, b2, hidden  []float64
}

// NewMLP returns a He-initialised network driven by rng.
func NewMLP(nIn, nHid, nOut int, lr float64, rng *rand.Rand) *MLP {
    nn := &MLP{
        lr: lr, nIn: nIn, nHid: nHid, nOut: nOut,
        w1: heMatrix(nIn, nHid, rng),
        w2: heMatrix(nHid, nOut, rng),
        b1: make([]float64, nHid),
        b2: make([]float64, nOut),
    }
    nn.hidden = make([]float64, nHid)
    return nn
}

// heMatrix fills a rows x cols matrix with N(0, 2/rows) values.
func heMatrix(rows, cols int, rng *rand.Rand) [][]float64 {
    scale := math.Sqrt(2 / float64(rows))
    m := make([][]float64, rows)
    for i := range m {
        m[i] = make([]float64, cols)
        for j := range m[i] {
            m[i][j] = rng.NormFloat64() * scale
        }
    }
    return m
}

func sigmoid(x float64) float64 { return 1 / (1 + math.Exp(-x)) }

// Forward computes the output for one sample and caches hidden activations.
func (nn *MLP) Forward(x []float64) []float64 {
    for j := range nn.hidden {
        s := nn.b1[j]
        for i, xi := range x {
            s += xi * nn.w1[i][j]
        }
        nn.hidden[j] = sigmoid(s)
    }
    out := make([]float64, nn.nOut)
    for k := range out {
        s := nn.b2[k]
        for j, h := range nn.hidden {
            s += h * nn.w2[j][k]
        }
        out[k] = sigmoid(s)
    }
    return out
}

// TrainStep performs one SGD update for a sample and returns its squared error.
func (nn *MLP) TrainStep(x, y []float64) float64 {
    out := nn.Forward(x)

    // Output delta: error times sigmoid'(out).
    dOut := make([]float64, nn.nOut)
    sqErr := 0.0
    for k, o := range out {
        dOut[k] = (o - y[k]) * o * (1 - o)
        sqErr += (o - y[k]) * (o - y[k])
    }

    // Hidden delta: backpropagated error times sigmoid'(hidden).
    dHid := make([]float64, nn.nHid)
    for j := range dHid {
        back := 0.0
        for k, d := range dOut {
            back += d * nn.w2[j][k]
        }
        dHid[j] = back * nn.hidden[j] * (1 - nn.hidden[j])
    }

    // Gradient descent: weight -= lr * delta * activation on that edge.
    for j, h := range nn.hidden {
        for k, d := range dOut {
            nn.w2[j][k] -= nn.lr * d * h
        }
    }
    for k, d := range dOut {
        nn.b2[k] -= nn.lr * d
    }
    for i, xi := range x {
        for j, d := range dHid {
            nn.w1[i][j] -= nn.lr * d * xi
        }
    }
    for j, d := range dHid {
        nn.b1[j] -= nn.lr * d
    }
    return sqErr
}

func main() {
    const (
        nIn, nHid, nOut = 4, 8, 2
        lr              = 0.5
        epochs          = 1000
    )

    // Deterministic PCG streams — no rand.Seed, reproducible across platforms.
    nn := NewMLP(nIn, nHid, nOut, lr, rand.New(rand.NewPCG(42, 0)))

    // Toy dataset — replace with your own.
    type sample struct{ x, y []float64 }
    data := rand.New(rand.NewPCG(7, 0))
    dataset := make([]sample, 64)
    for i := range dataset {
        dataset[i] = sample{x: make([]float64, nIn), y: make([]float64, nOut)}
        for j := range dataset[i].x {
            dataset[i].x[j] = data.Float64()
        }
        for k := range dataset[i].y {
            dataset[i].y[k] = data.Float64()
        }
    }

    showEvery := max(epochs/10, 1)
    for epoch := 1; epoch <= epochs; epoch++ {
        loss := 0.0
        for _, s := range dataset {
            loss += nn.TrainStep(s.x, s.y)
        }
        if epoch%showEvery == 0 {
            fmt.Printf("epoch %5d  mse = %.6f\n", epoch, loss/float64(len(dataset)))
        }
    }
}
