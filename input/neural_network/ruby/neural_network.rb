# frozen_string_literal: true

# neural_network.rb — idiomatic Ruby: stdlib `matrix` for all linear algebra,
# Struct value objects, endless method definitions, pattern matching.
# Run: ruby neural_network.rb   (Ruby 3.0+; `matrix` ships with Ruby)
#
# HOW IT WORKS
# ------------
# Network: n_in -> n_hidden (sigmoid) -> n_out (sigmoid), trained by SGD
# on mean squared error.
#
# FORWARD   hidden = sigmoid(W1.t * x + b1)        (Vector ops, whole-layer)
#           out    = sigmoid(W2 * hidden + b2)
#           sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)
#
# BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
#           d_out    = (out - y) * out * (1 - out)
#           d_hidden = (W2 * d_out) * hidden * (1 - hidden)
#
# UPDATE    every gradient = delta (outer) activation feeding that edge:
#           W2 -= lr * hidden.d_out     b2 -= lr * d_out
#           W1 -= lr * x.d_hidden       b1 -= lr * d_hidden
#           (column_vector * row_vector = outer product)
#
# Replace the "toy dataset" block below with real data to train on it.

require 'matrix'

HyperParameters = Struct.new(:n_in, :n_hidden, :n_out, :lr, keyword_init: true) do
  def validate
    raise ArgumentError, 'layer sizes must be positive' unless [n_in, n_hidden, n_out].all? { _1 >= 1 }
    raise ArgumentError, 'lr must be positive' unless lr.positive?

    self
  end
end

class NeuralNetwork
  attr_reader :hyper, :w1, :w2, :b1, :b2

  def initialize(hyper, rng: Random.new(42))
    @hyper = hyper.validate
    @w1 = he_matrix(hyper.n_in, hyper.n_hidden, rng)
    @b1 = Vector.zero(hyper.n_hidden)
    @w2 = he_matrix(hyper.n_hidden, hyper.n_out, rng)
    @b2 = Vector.zero(hyper.n_out)
  end

  # Forward pass for one input Vector; caches hidden activations.
  def forward(x)
    @hidden = (w1.t * x + b1).map { |z| sigmoid(z) }
    (w2 * @hidden + b2).map { |z| sigmoid(z) }
  end

  # One SGD step on one sample (Vectors); returns its squared error.
  def train_step(x, y)
    out = forward(x)
    y_vec = Vector.elements(y.to_a)

    # Deltas per the chain rule; sigmoid'(a) = a * (1 - a).
    d_out = out.map2(y_vec) { |o, t| (o - t) * o * (1 - o) }
    d_hidden = Vector.elements(
      (0...hyper.n_hidden).map do |j|
        a = @hidden[j]
        w2.row(j).inner_product(d_out) * a * (1 - a)
      end
    )

    # Outer-product weight updates; column * row = matrix of rank 1.
    @w2 -= Matrix.column_vector(@hidden) * Matrix.row_vector(d_out) * hyper.lr
    @b2 -= d_out * hyper.lr
    @w1 -= Matrix.column_vector(x) * Matrix.row_vector(d_hidden) * hyper.lr
    @b1 -= d_hidden * hyper.lr

    (out - y_vec).to_a.sum { |e| e * e }
  end

  private

  def sigmoid(z) = 1.0 / (1.0 + Math.exp(-z))

  def he_matrix(rows, cols, rng)
    scale = Math.sqrt(2.0 / rows)
    Matrix.build(rows, cols) { rng.gauss * scale }
  end
end

# ---- demo (replace with your own data) ------------------------------
EPOCHS = 1000

hyper = HyperParameters.new(n_in: 4, n_hidden: 8,
                            n_out: 2, lr: 0.5)
nn = NeuralNetwork.new(hyper)

rng = Random.new(7)
dataset = Array.new(64) do
  { x: Vector.elements(Array.new(hyper.n_in) { rng.rand }),
    y: Vector.elements(Array.new(hyper.n_out) { rng.rand }) }
end

show_every = [EPOCHS / 10, 1].max
(1..EPOCHS).each do |epoch|
  loss = dataset.sum do |sample|
    sample => { x:, y: }          # pattern-match destructuring
    nn.train_step(x, y)
  end
  puts format('epoch %5d  mse = %.6f', epoch, loss / dataset.size) if (epoch % show_every).zero?
end
