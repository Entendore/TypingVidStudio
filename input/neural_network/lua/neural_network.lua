-- neural_network.lua — idiomatic Lua: metatable OOP, colon syntax, 1-based
-- tables, cached math locals. Run: lua neural_network.lua  (Lua 5.1+/LuaJIT)
--
-- HOW IT WORKS
-- ------------
-- Network: n_in -> n_hidden (sigmoid) -> n_out (sigmoid), trained by SGD on MSE.
--
-- FORWARD   hidden[j] = sigmoid(b1[j] + sum_i x[i] * w1[i][j])
--           out[k]    = sigmoid(b2[k] + sum_j hidden[j] * w2[j][k])
--           sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)
--
-- BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
--           d_out[k]    = (out[k] - y[k]) * out[k] * (1 - out[k])
--           d_hidden[j] = (sum_k d_out[k] * w2[j][k]) * hidden[j] * (1 - hidden[j])
--
-- UPDATE    every gradient = delta * activation feeding that edge:
--           w2[j][k] -= lr * d_out[k] * hidden[j]    b2[k] -= lr * d_out[k]
--           w1[i][j] -= lr * d_hidden[j] * x[i]      b1[j] -= lr * d_hidden[j]
--
-- Lua tables are 1-based, so loops run 1..n.
-- Replace the "toy dataset" block at the bottom with real data to train on it.

local exp, sqrt, cos, log, pi = math.exp, math.sqrt, math.cos, math.log, math.pi
local floor, max = math.floor, math.max

local function sigmoid(x)
  return 1.0 / (1.0 + exp(-x))
end

-- Box-Muller standard normal (Lua has no built-in gaussian).
local function gauss()
  local u = math.random()
  while u == 0.0 do u = math.random() end
  return sqrt(-2.0 * log(u)) * cos(2.0 * pi * math.random())
end

-- He-style init: N(0, sqrt(2/rows)).
local function rand_matrix(rows, cols)
  local scale = sqrt(2.0 / rows)
  local m = {}
  for i = 1, rows do
    m[i] = {}
    for j = 1, cols do
      m[i][j] = gauss() * scale
    end
  end
  return m
end

local function zeros(n)
  local t = {}
  for i = 1, n do t[i] = 0.0 end
  return t
end

local NeuralNetwork = {}
NeuralNetwork.__index = NeuralNetwork

function NeuralNetwork.new(n_in, n_hid, n_out, lr)
  local self = setmetatable({}, NeuralNetwork)
  self.lr, self.n_in, self.n_hid, self.n_out = lr, n_in, n_hid, n_out
  self.w1 = rand_matrix(n_in, n_hid)
  self.b1 = zeros(n_hid)
  self.w2 = rand_matrix(n_hid, n_out)
  self.b2 = zeros(n_out)
  self.a1 = zeros(n_hid)
  return self
end

-- Forward pass; caches hidden activations in self.a1 for train_step.
function NeuralNetwork:forward(x)
  for j = 1, self.n_hid do
    local s = self.b1[j]
    for i = 1, self.n_in do
      s = s + x[i] * self.w1[i][j]
    end
    self.a1[j] = sigmoid(s)
  end
  local out = {}
  for k = 1, self.n_out do
    local s = self.b2[k]
    for j = 1, self.n_hid do
      s = s + self.a1[j] * self.w2[j][k]
    end
    out[k] = sigmoid(s)
  end
  return out
end

-- One SGD step; returns the sample's squared error.
function NeuralNetwork:train_step(x, y)
  local out = self:forward(x)

  -- Output delta: error times sigmoid'(out).
  local d2 = {}
  for k = 1, self.n_out do
    d2[k] = (out[k] - y[k]) * out[k] * (1.0 - out[k])
  end

  -- Hidden delta: backpropagated error times sigmoid'(hidden).
  local d1 = {}
  for j = 1, self.n_hid do
    local s = 0.0
    for k = 1, self.n_out do
      s = s + d2[k] * self.w2[j][k]
    end
    d1[j] = s * self.a1[j] * (1.0 - self.a1[j])
  end

  -- Gradient descent: weight -= lr * delta * activation on that edge.
  for j = 1, self.n_hid do
    for k = 1, self.n_out do
      self.w2[j][k] = self.w2[j][k] - self.lr * d2[k] * self.a1[j]
    end
  end
  for k = 1, self.n_out do
    self.b2[k] = self.b2[k] - self.lr * d2[k]
  end
  for i = 1, self.n_in do
    for j = 1, self.n_hid do
      self.w1[i][j] = self.w1[i][j] - self.lr * d1[j] * x[i]
    end
  end
  for j = 1, self.n_hid do
    self.b1[j] = self.b1[j] - self.lr * d1[j]
  end

  local sq = 0.0
  for k = 1, self.n_out do
    local d = out[k] - y[k]
    sq = sq + d * d
  end
  return sq
end

-- ---- demo (replace with your own data) ------------------------------
math.randomseed(42)
local N_IN, N_HID, N_OUT = 4, 8, 2
local LR, EPOCHS = 0.5, 1000

local nn = NeuralNetwork.new(N_IN, N_HID, N_OUT, LR)

math.randomseed(7)
local x, y = {}, {}
for s = 1, 64 do
  x[s], y[s] = {}, {}
  for i = 1, N_IN do x[s][i] = math.random() end
  for k = 1, N_OUT do y[s][k] = math.random() end
end

local show_every = max(floor(EPOCHS / 10), 1)
for ep = 1, EPOCHS do
  local loss = 0.0
  for s = 1, 64 do
    loss = loss + nn:train_step(x[s], y[s])
  end
  if ep % show_every == 0 then
    print(string.format("epoch %5d  mse = %.6f", ep, loss / 64))
  end
end
