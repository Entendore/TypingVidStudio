# neural_network.exs — idiomatic Elixir: immutable struct, pure functions
# returning {loss, net}, Enum.zip_with pipelines, comprehensions, :rand PRNG.
# Run: elixir neural_network.exs     (Elixir 1.12+, OTP 19+)
#
# HOW IT WORKS
# ------------
# Network: n_in -> n_hidden (sigmoid) -> n_out (sigmoid), trained by SGD on MSE.
#
# FORWARD   hidden[j] = sigmoid(b1[j] + dot(x, column j of w1))
#           out[k]    = sigmoid(b2[k] + dot(hidden, column k of w2))
#           sigmoid(z) = 1 / (1 + :math.exp(-z))  maps any value into (0,1)
#
# BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
#           d_out[k]    = (out[k] - y[k]) * out[k] * (1 - out[k])
#           d_hidden[j] = (sum_k d_out[k] * w2[j][k]) * hidden[j] * (1 - hidden[j])
#
# UPDATE    every gradient = delta * activation feeding that edge:
#           w2[j][k] -= lr * d_out[k] * hidden[j]    b2[k] -= lr * d_out[k]
#           w1[i][j] -= lr * d_hidden[j] * x[i]      b1[j] -= lr * d_hidden[j]
#
# Everything is immutable: train_step returns {sq_err, new_net}, and the
# demo threads the network through epochs with Enum.reduce/map_reduce.
# Replace the "toy dataset" block at the bottom with real data to train on it.

defmodule NeuralNetwork do
  @moduledoc "One-hidden-layer MLP with sigmoid activations, trained by SGD."

  defstruct [:lr, :w1, :b1, :w2, :b2]

  def new(n_in, n_hidden, n_out, lr, seed \\ 42) do
    :rand.seed(:exsss, seed)

    %__MODULE__{
      lr: lr,
      w1: he_matrix(n_in, n_hidden),   # He-style init
      b1: List.duplicate(0.0, n_hidden),
      w2: he_matrix(n_hidden, n_out),
      b2: List.duplicate(0.0, n_out)
    }
  end

  defp he_matrix(rows, cols) do
    scale = :math.sqrt(2 / rows)

    for _ <- 1..rows do
      for _ <- 1..cols, do: :rand.normal(0.0, 1.0) * scale
    end
  end

  defp sigmoid(x), do: 1 / (1 + :math.exp(-x))

  defp dot(a, b), do: Enum.zip_with(a, b, &*/2) |> Enum.sum()

  # List.zip pairs corresponding rows — the classic Elixir transpose trick.
  defp transpose(rows), do: rows |> List.zip() |> Enum.map(&Tuple.to_list/1)

  @doc "Returns {hidden, output} activations for one sample."
  def forward(%__MODULE__{w1: w1, b1: b1, w2: w2, b2: b2}, x) do
    hidden =
      b1
      |> Enum.zip(transpose(w1))
      |> Enum.map(fn {b, col} -> sigmoid(b + dot(x, col)) end)

    out =
      b2
      |> Enum.zip(transpose(w2))
      |> Enum.map(fn {b, col} -> sigmoid(b + dot(hidden, col)) end)

    {hidden, out}
  end

  @doc "One SGD step; returns {squared_error, updated_network}."
  def train_step(%__MODULE__{lr: lr} = net, x, y) do
    {hidden, out} = forward(net, x)

    # Output delta: error times sigmoid'(out).
    d_out = Enum.zip_with(out, y, fn o, t -> (o - t) * o * (1 - o) end)

    # Hidden delta: backpropagated error times sigmoid'(hidden).
    d_hidden =
      hidden
      |> Enum.zip(net.w2)
      |> Enum.map(fn {h, row} -> dot(d_out, row) * h * (1 - h) end)

    # Gradient descent: weight -= lr * delta * activation on that edge.
    w2 =
      net.w2
      |> Enum.zip(hidden)
      |> Enum.map(fn {row, h} ->
        Enum.zip_with(row, d_out, fn w, d -> w - lr * d * h end)
      end)

    b2 = Enum.zip_with(net.b2, d_out, fn b, d -> b - lr * d end)

    w1 =
      net.w1
      |> Enum.zip(x)
      |> Enum.map(fn {row, xi} ->
        Enum.zip_with(row, d_hidden, fn w, d -> w - lr * d * xi end)
      end)

    b1 = Enum.zip_with(net.b1, d_hidden, fn b, d -> b - lr * d end)

    sq_err =
      Enum.zip_with(out, y, fn o, t ->
        d = o - t
        d * d
      end)
      |> Enum.sum()

    {sq_err, %{net | w1: w1, b1: b1, w2: w2, b2: b2}}
  end
end

# ---- demo (replace with your own data) ----------------------------------
n_in = 4
n_hidden = 8
n_out = 2
lr = 0.5
epochs = 1000

:rand.seed(:exsss, 7)

dataset =
  for _ <- 1..64 do
    {for _ <- 1..n_in, do: :rand.uniform(),
     for _ <- 1..n_out, do: :rand.uniform()}
  end

net = NeuralNetwork.new(n_in, n_hidden, n_out, lr, 42)
show_every = max(div(epochs, 10), 1)

# Enum.map_reduce threads the network through the dataset — the idiomatic
# way to fold a stateful accumulator over a collection.
_final_net =
  Enum.reduce(1..epochs, net, fn epoch, net ->
    {losses, net} =
      Enum.map_reduce(dataset, net, fn {x, y}, acc ->
        NeuralNetwork.train_step(acc, x, y)
      end)

    if rem(epoch, show_every) == 0 do
      mse = Enum.sum(losses) / 64

      IO.puts(
        "epoch #{String.pad_leading(Integer.to_string(epoch), 5)}  " <>
          "mse = #{:erlang.float_to_binary(mse, decimals: 6)}"
      )
    end

    net
  end)
