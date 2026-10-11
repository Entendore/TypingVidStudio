// neural_network.groovy — idiomatic Groovy: GDK collections (transpose, sum,
// exclusive ranges), implicit closure destructuring, @Canonical map
// constructors, printf output. Run: groovy neural_network.groovy
//
// HOW IT WORKS
// ------------
// Network: nIn -> nHidden (sigmoid) -> nOut (sigmoid), trained by SGD on MSE.
//
// FORWARD   hidden[j] = sigmoid(b1[j] + dot(x, column j of w1))
//           out[k]    = sigmoid(b2[k] + dot(hidden, column k of w2))
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

import groovy.transform.Canonical

@Canonical
class HyperParams {
    int nIn
    int nHidden
    int nOut
    double lr
}

class NeuralNetwork {
    final HyperParams hp
    private final Random rng
    List<List<Double>> w1, w2
    List<Double> b1, b2
    private List<Double> hidden

    NeuralNetwork(HyperParams hp, long seed = 42L) {
        this.hp = hp
        this.rng = new Random(seed)
        w1 = heMatrix(hp.nIn, hp.nHidden)     // He-style init
        b1 = [0d] * hp.nHidden                // list repetition — GDK idiom
        w2 = heMatrix(hp.nHidden, hp.nOut)
        b2 = [0d] * hp.nOut
    }

    private List<List<Double>> heMatrix(int rows, int cols) {
        double scale = Math.sqrt(2d / rows)
        (1..rows).collect { (1..cols).collect { rng.nextGaussian() * scale } }
    }

    private static double sigmoid(double z) { 1d / (1d + Math.exp(-z)) }

    // transpose() of two vectors pairs them up; Groovy then spreads each
    // pair onto the closure's two parameters.
    private static double dot(List<Double> a, List<Double> b) {
        [a, b].transpose().sum { x, y -> x * y }
    }

    /** Forward pass; caches hidden activations for trainStep. */
    List<Double> forward(List<Double> x) {
        hidden = (0..<hp.nHidden).collect { j -> sigmoid(b1[j] + dot(x, w1.collect { it[j] })) }
        (0..<hp.nOut).collect { k -> sigmoid(b2[k] + dot(hidden, w2.collect { it[k] })) }
    }

    /** One SGD step; returns the sample's squared error. */
    double trainStep(List<Double> x, List<Double> y) {
        def out = forward(x)
        def dOut = [out, y].transpose().collect { o, t -> (o - t) * o * (1 - o) }
        def dHidden = (0..<hp.nHidden).collect { j ->
            dot(dOut, w2[j]) * hidden[j] * (1 - hidden[j])
        }

        w2 = [w2, hidden].transpose().collect { row, h ->
            [row, dOut].transpose().collect { w, d -> w - hp.lr * d * h }
        }
        b2 = [b2, dOut].transpose().collect { b, d -> b - hp.lr * d }
        w1 = [w1, x].transpose().collect { row, xi ->
            [row, dHidden].transpose().collect { w, d -> w - hp.lr * d * xi }
        }
        b1 = [b1, dHidden].transpose().collect { b, d -> b - hp.lr * d }

        [out, y].transpose().collect { o, t -> (o - t) * (o - t) }.sum()
    }
}

// ---- demo (replace with your own data) ----------------------------------
def hp = new HyperParams(nIn: 4, nHidden: 8,
                         nOut: 2, lr: 0.5)   // @Canonical map constructor
int epochs = 1000
def net = new NeuralNetwork(hp)

def data = new Random(7)
def dataset = (1..64).collect {
    [x: (1..hp.nIn).collect { data.nextDouble() },
     y: (1..hp.nOut).collect { data.nextDouble() }]
}

int showEvery = Math.max(epochs.intdiv(10), 1)
(1..epochs).each { epoch ->
    double loss = dataset.sum { net.trainStep(it.x, it.y) }   // sum(closure)
    if (epoch % showEvery == 0) {
        printf "epoch %5d  mse = %.6f%n", epoch, loss / dataset.size()
    }
}
