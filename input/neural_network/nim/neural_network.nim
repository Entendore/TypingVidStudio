## neural_network.nim — idiomatic Nim: std/random gauss, sugar.collect
## comprehensions, openArray params, `result`, strformat.
## Run:
##   nim c -d:release -o:nn neural_network.nim && ./nn    (Nim 1.6+)
##
## HOW IT WORKS
## ------------
## Network: nIn -> nHidden (sigmoid) -> nOut (sigmoid), trained by SGD on MSE.
##
## FORWARD   hidden[j] = sigmoid(b1[j] + sum_i x[i] * w1[i][j])
##           output[k] = sigmoid(b2[k] + sum_j hidden[j] * w2[j][k])
##           sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)
##
## BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
##           dOut[k]    = (output[k] - y[k]) * output[k] * (1 - output[k])
##           dHidden[j] = (sum_k dOut[k] * w2[j][k]) * hidden[j] * (1 - hidden[j])
##
## UPDATE    every gradient = delta * activation feeding that edge:
##           w2[j][k] -= lr * dOut[k] * hidden[j]     b2[k] -= lr * dOut[k]
##           w1[i][j] -= lr * dHidden[j] * x[i]       b1[j] -= lr * dHidden[j]
##
## Replace the "toy dataset" block at the bottom with real data to train on it.

import std/[math, random, sequtils, strformat, sugar]

type
  HyperParams = object
    nIn, nHidden, nOut: int
    lr: float

  Mlp = object
    hp: HyperParams
    w1, w2: seq[seq[float]]
    b1, b2, hidden: seq[float]

func sigmoid(x: float): float {.inline.} = 1.0 / (1.0 + exp(-x))

func dot(a, b: openArray[float]): float {.inline.} =
  sum(mapIt(0 ..< a.len, a[it] * b[it]))

proc heMatrix(rows, cols: int): seq[seq[float]] =
  ## He-initialised weights; std/random already seeded by the caller.
  let scale = sqrt(2.0 / rows.toFloat)
  collect(newSeq):
    for _ in 0 ..< rows:
      collect(newSeq):
        for _ in 0 ..< cols:
          gauss() * scale

proc newMlp(hp: HyperParams, seed: int64): Mlp =
  randomize(seed)
  Mlp(
    hp: hp,
    w1: heMatrix(hp.nIn, hp.nHidden),
    b1: newSeq[float](hp.nHidden),
    w2: heMatrix(hp.nHidden, hp.nOut),
    b2: newSeq[float](hp.nOut),
    hidden: newSeq[float](hp.nHidden))

proc forward(m: var Mlp, x: openArray[float]): seq[float] =
  for j in 0 ..< m.hp.nHidden:
    var z = m.b1[j]
    for i in 0 ..< m.hp.nIn:
      z += x[i] * m.w1[i][j]
    m.hidden[j] = sigmoid(z)
  for k in 0 ..< m.hp.nOut:
    var z = m.b2[k]
    for j in 0 ..< m.hp.nHidden:
      z += m.hidden[j] * m.w2[j][k]
    result.add sigmoid(z)          # the classic `result` idiom

proc trainStep(m: var Mlp, x, y: openArray[float]): float =
  let output = forward(m, x)

  # Output delta: error times sigmoid'(out).
  let dOut = collect(newSeq):
    for k in 0 ..< m.hp.nOut:
      (output[k] - y[k]) * output[k] * (1.0 - output[k])

  # Hidden delta: backpropagated error times sigmoid'(hidden).
  let dHidden = collect(newSeq):
    for j in 0 ..< m.hp.nHidden:
      dot(dOut, m.w2[j]) * m.hidden[j] * (1.0 - m.hidden[j])

  # Gradient descent: weight -= lr * delta * activation on that edge.
  for j in 0 ..< m.hp.nHidden:
    for k in 0 ..< m.hp.nOut:
      m.w2[j][k] -= m.hp.lr * dOut[k] * m.hidden[j]
  for k in 0 ..< m.hp.nOut:
    m.b2[k] -= m.hp.lr * dOut[k]
  for i in 0 ..< m.hp.nIn:
    for j in 0 ..< m.hp.nHidden:
      m.w1[i][j] -= m.hp.lr * dHidden[j] * x[i]
  for j in 0 ..< m.hp.nHidden:
    m.b1[j] -= m.hp.lr * dHidden[j]

  let sq = collect(newSeq):
    for k in 0 ..< m.hp.nOut:
      let d = output[k] - y[k]
      d * d
  sum(sq)

when isMainModule:
  let hp = HyperParams(nIn: 4, nHidden: 8,
                       nOut: 2, lr: 0.5)
  let epochs = 1000
  var net = newMlp(hp, seed = 42)

  randomize(7)  # toy dataset — replace with your own
  let xs = collect(newSeq):
    for _ in 0 ..< 64:
      collect(newSeq):
        for _ in 0 ..< hp.nIn: rand(1.0)
  let ys = collect(newSeq):
    for _ in 0 ..< 64:
      collect(newSeq):
        for _ in 0 ..< hp.nOut: rand(1.0)
  let dataset = zip(xs, ys)

  let showEvery = max(epochs div 10, 1)
  for epoch in 1 .. epochs:
    var loss = 0.0
    for (x, y) in dataset:
      loss += net.trainStep(x, y)
    if epoch mod showEvery == 0:
      let mse = loss / dataset.len.toFloat
      echo &"epoch {epoch:5}  mse = {mse:.6f}"
