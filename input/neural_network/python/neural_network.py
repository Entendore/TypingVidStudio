#!/usr/bin/env python3
"""One-hidden-layer MLP — idiomatic NumPy (Generator API, dataclass, type hints).

HOW IT WORKS
------------
Network: n_in -> n_hidden (sigmoid) -> n_out (sigmoid), trained by SGD
on mean squared error.

FORWARD   hidden[j] = sigmoid(b1[j] + sum_i x[i] * W1[i][j])
          out[k]    = sigmoid(b2[k] + sum_j hidden[j] * W2[j][k])
          sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)

BACKPROP  (chain rule; the derivative of sigmoid at output a is a*(1-a)):
          dOut[k]    = (out[k] - y[k]) * out[k] * (1 - out[k])
          dHidden[j] = (sum_k dOut[k] * W2[j][k]) * hidden[j] * (1 - hidden[j])

UPDATE    every gradient = delta * activation feeding that edge:
          W2[j][k] -= lr * dOut[k] * hidden[j]     b2[k] -= lr * dOut[k]
          W1[i][j] -= lr * dHidden[j] * x[i]       b1[j] -= lr * dHidden[j]

Replace the "toy dataset" block in main() with real data to train on it.
Run: python neural_network.py   (requires: pip install numpy)
"""

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

Array = npt.NDArray[np.float64]


def sigmoid(x: Array) -> Array:
    return 1.0 / (1.0 + np.exp(-x))


@dataclass(frozen=True)
class Config:
    """Hyperparameters, validated on construction."""

    n_in: int
    n_hidden: int
    n_out: int
    lr: float

    def __post_init__(self) -> None:
        if min(self.n_in, self.n_hidden, self.n_out) < 1:
            raise ValueError("layer sizes must be positive")
        if self.lr <= 0.0:
            raise ValueError("learning rate must be positive")


class NeuralNetwork:
    def __init__(self, cfg: Config, *, seed: int = 42) -> None:
        self.cfg = cfg
        rng = np.random.default_rng(seed)  # modern Generator API
        # He-style init: variance scaled by fan-in so activations stay healthy.
        self.w1 = rng.standard_normal((cfg.n_in, cfg.n_hidden)) * np.sqrt(2 / cfg.n_in)
        self.b1 = np.zeros(cfg.n_hidden)
        self.w2 = rng.standard_normal((cfg.n_hidden, cfg.n_out)) * np.sqrt(2 / cfg.n_hidden)
        self.b2 = np.zeros(cfg.n_out)
        self.a1: Array | None = None

    def forward(self, x: Array) -> Array:
        self.a1 = sigmoid(x @ self.w1 + self.b1)          # layer 1
        return sigmoid(self.a1 @ self.w2 + self.b2)       # layer 2

    def sgd_step(self, x: Array, y: Array) -> float:
        """One full-batch gradient step; returns the batch MSE."""
        out = self.forward(x)
        n = x.shape[0]

        # Backprop: error signal flows output -> hidden via W2.T
        delta2 = (out - y) * out * (1.0 - out)            # sigmoid'(out) factored in
        delta1 = (delta2 @ self.w2.T) * self.a1 * (1.0 - self.a1)

        # Gradients are delta (next layer) x activation (this layer)
        self.w2 -= self.cfg.lr * (self.a1.T @ delta2) / n
        self.b2 -= self.cfg.lr * delta2.mean(axis=0)
        self.w1 -= self.cfg.lr * (x.T @ delta1) / n
        self.b1 -= self.cfg.lr * delta1.mean(axis=0)
        return float(np.mean((out - y) ** 2))


def train(net: NeuralNetwork, x: Array, y: Array, epochs: int) -> list[float]:
    history: list[float] = []
    for epoch in range(1, epochs + 1):
        mse = net.sgd_step(x, y)
        history.append(mse)
        if epoch % max(epochs // 10, 1) == 0:
            print(f"epoch {epoch:5d}  mse = {mse:.6f}")
    return history


def main() -> None:
    cfg = Config(n_in=4, n_hidden=8, n_out=2, lr=0.5)
    rng = np.random.default_rng(7)  # toy data — replace with your own
    x = rng.random((64, cfg.n_in))
    y = rng.random((64, cfg.n_out))

    net = NeuralNetwork(cfg)
    history = train(net, x, y, epochs=1000)
    print(f"\nfinal mse = {history[-1]:.6f}")
    print(np.round(net.forward(x[:5]), 3))


if __name__ == "__main__":
    main()
