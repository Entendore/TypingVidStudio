# neural_network.jl — idiomatic Julia: concrete parametrized struct,
# Random.Xoshiro, docstrings, Logging (@info), Base.show, unicode gradients.
# Run: julia neural_network.jl   (Julia 1.7+)
#
# HOW IT WORKS
# ------------
# Network: n_in -> n_hidden (sigmoid) -> n_out (sigmoid), trained by
# full-batch SGD on mean squared error.
#
# FORWARD   hidden = sigmoid.(X * W1 .+ b1')      (whole-batch broadcasting)
#           out    = sigmoid.(hidden * W2 .+ b2')
#           sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)
#
# BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
#           δ2 = (out .- y) .* out .* (1 .- out)
#           δ1 = (δ2 * W2') .* hidden .* (1 .- hidden)
#
# UPDATE    gradients via transposed matmuls, averaged over the batch:
#           W2 .-= lr .* (hidden' * δ2) ./ m     b2 .-= lr .* vec(sum(δ2, dims=1)) ./ m
#           W1 .-= lr .* (X' * δ1) ./ m          b1 .-= lr .* vec(sum(δ1, dims=1)) ./ m
#
# Replace the "toy dataset" block at the bottom with real data to train on it.

using Random, Logging

"Elementwise logistic activation."
sigmoid(x) = 1 / (1 + exp(-x))

"""
    NeuralNetwork(n_in, n_hidden, n_out, lr; rng = Random.Xoshiro(42))

A one-hidden-layer MLP with sigmoid activations and He-initialised weights.
Type parameters keep the struct concrete — no abstract-typed fields.
"""
struct NeuralNetwork{M1,V1,M2,V2}
    lr::Float64
    W1::M1
    b1::V1
    W2::M2
    b2::V2
end

function NeuralNetwork(n_in::Int, n_hidden::Int, n_out::Int, lr::Real;
                       rng::AbstractRNG = Random.Xoshiro(42))
    NeuralNetwork(
        Float64(lr),
        randn(rng, n_in, n_hidden) .* sqrt(2 / n_in),
        zeros(n_hidden),
        randn(rng, n_hidden, n_out) .* sqrt(2 / n_hidden),
        zeros(n_out),
    )
end

"Human-readable summary via the display system."
function Base.show(io::IO, ::MIME"text/plain", net::NeuralNetwork)
    print(io, "NeuralNetwork($(size(net.W1, 1)) → $(size(net.W1, 2)) → ",
          "$(size(net.W2, 2)), lr = $(net.lr))")
end

"Forward pass for a batch `X` (rows = observations); returns the output matrix."
forward(net::NeuralNetwork, X::AbstractMatrix) =
    sigmoid.(sigmoid.(X * net.W1 .+ net.b1') * net.W2 .+ net.b2')

"""
    train!(net; X, y, epochs = 1000, show_every = max(epochs ÷ 10, 1))

Full-batch SGD, mutating `net` in place (the `!` convention).
"""
function train!(net::NeuralNetwork; X, y, epochs::Integer = 1000,
                show_every = max(epochs ÷ 10, 1))
    m = size(X, 1)
    for epoch in 1:epochs
        hidden = sigmoid.(X * net.W1 .+ net.b1')
        out = sigmoid.(hidden * net.W2 .+ net.b2')

        # Deltas per the chain rule (δ = error signal per layer).
        δ2 = (out .- y) .* out .* (1 .- out)
        δ1 = (δ2 * net.W2') .* hidden .* (1 .- hidden)

        # Gradient descent with transposed matmuls as outer products.
        net.W2 .-= net.lr .* (hidden' * δ2) ./ m
        net.b2 .-= net.lr .* vec(sum(δ2; dims = 1)) ./ m
        net.W1 .-= net.lr .* (X' * δ1) ./ m
        net.b1 .-= net.lr .* vec(sum(δ1; dims = 1)) ./ m

        epoch % show_every == 0 && @info "training" epoch mse = sum(abs2, out .- y) / length(y)
    end
    return net
end

# ---- demo (replace with your own data) ----------------------------------
const N_IN, N_HIDDEN, N_OUT = 4, 8, 2
const LEARNING_RATE, EPOCHS = 0.5, 1000

data_rng = Random.Xoshiro(7)          # explicit local RNG — no global seed
X = rand(data_rng, 64, N_IN)
y = rand(data_rng, 64, N_OUT)

net = NeuralNetwork(N_IN, N_HIDDEN, N_OUT, LEARNING_RATE)
display(net)
train!(net; X, y, epochs = EPOCHS)

println("\nfirst 5 predictions:")
display(round.(forward(net, X[1:5, :]); digits = 3))
