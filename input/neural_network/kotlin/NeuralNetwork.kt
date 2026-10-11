// NeuralNetwork.kt — idiomatic Kotlin: data class with require() validation,
// extension functions, DoubleArray + sumOf, destructuring, named args.
// Run: kotlinc NeuralNetwork.kt -include-runtime -d nn.jar && java -jar nn.jar
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
// Replace the "toy dataset" block in main() with real data to train on it.

import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.exp
import kotlin.math.ln
import kotlin.math.sqrt
import kotlin.random.Random

/** Hyperparameters, validated in the init block. */
data class HyperParameters(
    val nIn: Int,
    val nHidden: Int,
    val nOut: Int,
    val lr: Double,
) {
    init {
        require(listOf(nIn, nHidden, nOut).all { it > 0 }) { "layer sizes must be positive" }
        require(lr > 0.0) { "lr must be positive" }
    }
}

/** Box-Muller transform as an extension on kotlin.random.Random. */
fun Random.gaussian(): Double {
    var u = nextDouble()
    while (u == 0.0) u = nextDouble()
    return sqrt(-2.0 * ln(u)) * cos(2.0 * PI * nextDouble())
}

class NeuralNetwork(
    private val hyper: HyperParameters,
    seed: Long = 42L,
) {
    private val rng = Random(seed)
    private val w1 = heMatrix(hyper.nIn, hyper.nHidden)
    private val b1 = DoubleArray(hyper.nHidden)
    private val w2 = heMatrix(hyper.nHidden, hyper.nOut)
    private val b2 = DoubleArray(hyper.nOut)
    private var hidden = DoubleArray(hyper.nHidden)

    private fun heMatrix(rows: Int, cols: Int): Array<DoubleArray> {
        val scale = sqrt(2.0 / rows)
        return Array(rows) { DoubleArray(cols) { rng.gaussian() * scale } }
    }

    private fun sigmoid(x: Double): Double = 1.0 / (1.0 + exp(-x))

    /** Forward pass for one sample; caches hidden activations. */
    fun forward(x: DoubleArray): DoubleArray {
        hidden = DoubleArray(hyper.nHidden) { j ->
            sigmoid(b1[j] + x.indices.sumOf { x[it] * w1[it][j] })
        }
        return DoubleArray(hyper.nOut) { k ->
            sigmoid(b2[k] + hidden.indices.sumOf { hidden[it] * w2[it][k] })
        }
    }

    /** One SGD step for one sample; returns its squared error. */
    fun trainStep(x: DoubleArray, y: DoubleArray): Double {
        val out = forward(x)

        // Output delta: error times sigmoid'(out).
        val dOut = DoubleArray(hyper.nOut) { k -> (out[k] - y[k]) * out[k] * (1 - out[k]) }
        // Hidden delta: backpropagated error times sigmoid'(hidden).
        val dHidden = DoubleArray(hyper.nHidden) { j ->
            val back = dOut.indices.sumOf { dOut[it] * w2[j][it] }
            back * hidden[j] * (1 - hidden[j])
        }

        // Gradient descent: weight -= lr * delta * activation on that edge.
        for (j in w2.indices) {
            val row = w2[j]
            for (k in row.indices) row[k] -= hyper.lr * dOut[k] * hidden[j]
        }
        for (k in b2.indices) b2[k] -= hyper.lr * dOut[k]
        for (i in w1.indices) {
            val row = w1[i]
            for (j in row.indices) row[j] -= hyper.lr * dHidden[j] * x[i]
        }
        for (j in b1.indices) b1[j] -= hyper.lr * dHidden[j]
        return dOut.indices.sumOf { k -> (out[k] - y[k]) * (out[k] - y[k]) }
    }
}

fun main() {
    val hyper = HyperParameters(nIn = 4, nHidden = 8, nOut = 2, lr = 0.5)
    val epochs = 1000
    val net = NeuralNetwork(hyper, seed = 42L)

    // Toy dataset — replace with your own.
    val data = Random(7)
    val samples = List(64) {
        DoubleArray(hyper.nIn) { data.nextDouble() } to DoubleArray(hyper.nOut) { data.nextDouble() }
    }

    val showEvery = maxOf(epochs / 10, 1)
    for (epoch in 1..epochs) {
        val loss = samples.sumOf { (x, y) -> net.trainStep(x, y) }   // destructuring
        if (epoch % showEvery == 0) {
            println("epoch %5d  mse = %.6f".format(epoch, loss / samples.size))
        }
    }
}
