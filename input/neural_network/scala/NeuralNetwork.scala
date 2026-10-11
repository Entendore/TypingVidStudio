//> using scala 3.3.3

// NeuralNetwork.scala — idiomatic Scala 3: case classes with require(),
// significant indentation, top-level extension methods, Array.tabulate,
// @main entry point, f-interpolator. Run: scala-cli run NeuralNetwork.scala
//
// HOW IT WORKS
// ------------
// Network: nIn -> nHidden (sigmoid) -> nOut (sigmoid), trained by SGD on MSE.
//
// FORWARD   hidden[j] = sigmoid(b1(j) + sum_i x(i) * w1(i)(j))
//           out[k]    = sigmoid(b2(k) + sum_j hidden(j) * w2(j)(k))
//           sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)
//
// BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
//           dOut(k)    = (out(k) - y(k)) * out(k) * (1 - out(k))
//           dHidden(j) = (sum_k dOut(k) * w2(j)(k)) * hidden(j) * (1 - hidden(j))
//
// UPDATE    every gradient = delta * activation feeding that edge:
//           w2(j)(k) -= lr * dOut(k) * hidden(j)     b2(k) -= lr * dOut(k)
//           w1(i)(j) -= lr * dHidden(j) * x(i)       b1(j) -= lr * dHidden(j)
//
// Replace the "toy dataset" block in demo() with real data to train on it.

import scala.util.Random

/** Hyperparameters, validated at construction. */
final case class HyperParams(nIn: Int, nHidden: Int, nOut: Int, lr: Double, epochs: Int):
  require(nIn > 0 && nHidden > 0 && nOut > 0, "layer sizes must be positive")
  require(lr > 0, "learning rate must be positive")

extension (v: Array[Double])
  /** v · w[:, col] — a column of a row-major matrix. */
  def dotCol(w: Array[Array[Double]], col: Int): Double =
    v.indices.foldLeft(0.0)((acc, i) => acc + v(i) * w(i)(col))

/** One-hidden-layer MLP trained with per-sample SGD. */
final class NeuralNetwork(hp: HyperParams, seed: Long = 42L):
  private val nIn = hp.nIn
  private val nHidden = hp.nHidden
  private val nOut = hp.nOut
  private val lr = hp.lr
  private val rng = Random(seed)

  private val w1 = heMatrix(nIn, nHidden)     // He-style init
  private val b1 = Array.fill(nHidden)(0.0)
  private val w2 = heMatrix(nHidden, nOut)
  private val b2 = Array.fill(nOut)(0.0)
  private var hidden: Array[Double] = Array.empty

  private def heMatrix(rows: Int, cols: Int): Array[Array[Double]] =
    val scale = math.sqrt(2.0 / rows)
    Array.tabulate(rows, cols)((_, _) => rng.nextGaussian() * scale)

  /** Forward pass; caches hidden activations for trainStep. */
  def forward(x: Array[Double]): Array[Double] =
    hidden = Array.tabulate(nHidden)(j => sigmoid(b1(j) + x.dotCol(w1, j)))
    Array.tabulate(nOut)(k => sigmoid(b2(k) + hidden.dotCol(w2, k)))

  /** One SGD step; returns the sample's squared error. */
  def trainStep(x: Array[Double], y: Array[Double]): Double =
    val out = forward(x)

    // Output delta: error times sigmoid'(out).
    val dOut = (out zip y).map { case (o, t) => (o - t) * o * (1 - o) }
    // Hidden delta: backpropagated error times sigmoid'(hidden).
    val dHidden = Array.tabulate(nHidden) { j =>
      val back = dOut.zip(w2(j)).map(_ * _).sum
      back * hidden(j) * (1 - hidden(j))
    }

    // Gradient descent: weight -= lr * delta * activation on that edge.
    for j <- w2.indices; k <- dOut.indices do w2(j)(k) -= lr * dOut(k) * hidden(j)
    for k <- b2.indices do b2(k) -= lr * dOut(k)
    for i <- w1.indices; j <- dHidden.indices do w1(i)(j) -= lr * dHidden(j) * x(i)
    for j <- b1.indices do b1(j) -= lr * dHidden(j)

    (out zip y).map { case (o, t) => val d = o - t; d * d }.sum

  private def sigmoid(z: Double): Double = 1.0 / (1.0 + math.exp(-z))

@main def demo(): Unit =
  val hp = HyperParams(nIn = 4, nHidden = 8, nOut = 2,
                       lr = 0.5, epochs = 1000)
  val net = NeuralNetwork(hp)

  val data = Random(7)  // toy dataset — replace with your own
  val dataset = List.fill(64):
    (Array.fill(hp.nIn)(data.nextDouble()),
     Array.fill(hp.nOut)(data.nextDouble()))

  val showEvery = math.max(hp.epochs / 10, 1)
  for epoch <- 1 to hp.epochs do
    val loss = dataset.map((x, y) => net.trainStep(x, y)).sum
    if epoch % showEvery == 0 then
      println(f"epoch $epoch%5d  mse = ${loss / dataset.size}%.6f")
