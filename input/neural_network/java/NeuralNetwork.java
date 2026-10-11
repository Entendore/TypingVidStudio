// NeuralNetwork.java — idiomatic Java 17+: records with compact-constructor
// validation, RandomGenerator.nextGaussian(), Arrays.setAll, streams for
// orchestration (plain loops in hot paths).
// Run: javac NeuralNetwork.java && java NeuralNetwork
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

import java.util.Arrays;
import java.util.Random;
import java.util.random.RandomGenerator;
import java.util.stream.IntStream;

/** Hyperparameters; the compact constructor validates them. */
record HyperParams(int nIn, int nHidden, int nOut, double lr, int epochs) {
    HyperParams {
        if (nIn < 1 || nHidden < 1 || nOut < 1)
            throw new IllegalArgumentException("layer sizes must be positive");
        if (lr <= 0) throw new IllegalArgumentException("lr must be positive");
    }
}

/** One-hidden-layer MLP trained with per-sample SGD. */
final class NeuralNetwork {

    private final int nIn, nHidden, nOut;
    private final double lr;
    private final double[][] w1, w2;
    private final double[] b1, b2;
    private double[] hidden;  // activations cached for backprop

    NeuralNetwork(HyperParams hp, RandomGenerator rng) {
        this.nIn = hp.nIn();
        this.nHidden = hp.nHidden();
        this.nOut = hp.nOut();
        this.lr = hp.lr();
        this.w1 = heMatrix(hp.nIn(), hp.nHidden(), rng);
        this.w2 = heMatrix(hp.nHidden(), hp.nOut(), rng);
        this.b1 = new double[hp.nHidden()];
        this.b2 = new double[hp.nOut()];
    }

    private static double[][] heMatrix(int rows, int cols, RandomGenerator rng) {
        double scale = Math.sqrt(2.0 / rows);
        double[][] m = new double[rows][cols];
        for (double[] row : m)
            Arrays.setAll(row, j -> rng.nextGaussian() * scale);  // He-style init
        return m;
    }

    double[] forward(double[] x) {
        hidden = new double[nHidden];
        for (int j = 0; j < nHidden; j++) {
            double z = b1[j];
            for (int i = 0; i < nIn; i++) z += x[i] * w1[i][j];
            hidden[j] = sigmoid(z);
        }
        double[] out = new double[nOut];
        for (int k = 0; k < nOut; k++) {
            double z = b2[k];
            for (int j = 0; j < nHidden; j++) z += hidden[j] * w2[j][k];
            out[k] = sigmoid(z);
        }
        return out;
    }

    /** One SGD step; returns the sample's squared error. */
    double trainStep(double[] x, double[] y) {
        double[] out = forward(x);

        // Output delta: error times sigmoid'(out) = out*(1-out).
        double[] dOut = new double[nOut];
        double sqErr = 0.0;
        for (int k = 0; k < nOut; k++) {
            double d = out[k] - y[k];
            dOut[k] = d * out[k] * (1 - out[k]);
            sqErr += d * d;
        }

        // Hidden delta: backpropagated error times sigmoid'(hidden).
        double[] dHidden = new double[nHidden];
        for (int j = 0; j < nHidden; j++) {
            double back = 0.0;
            for (int k = 0; k < nOut; k++) back += dOut[k] * w2[j][k];
            dHidden[j] = back * hidden[j] * (1 - hidden[j]);
        }

        // Gradient descent: weight -= lr * delta * activation on that edge.
        for (int j = 0; j < nHidden; j++)
            for (int k = 0; k < nOut; k++) w2[j][k] -= lr * dOut[k] * hidden[j];
        for (int k = 0; k < nOut; k++) b2[k] -= lr * dOut[k];
        for (int i = 0; i < nIn; i++)
            for (int j = 0; j < nHidden; j++) w1[i][j] -= lr * dHidden[j] * x[i];
        for (int j = 0; j < nHidden; j++) b1[j] -= lr * dHidden[j];
        return sqErr;
    }

    private static double sigmoid(double x) { return 1.0 / (1.0 + Math.exp(-x)); }

    public static void main(String[] args) {
        var hp = new HyperParams(4, 8, 2, 0.5, 1000);
        var net = new NeuralNetwork(hp, new Random(42));

        // Toy dataset — replace with your own.
        var data = new Random(7);
        double[][] x = new double[64][hp.nIn()];
        double[][] y = new double[64][hp.nOut()];
        for (double[] row : x) Arrays.setAll(row, i -> data.nextDouble());
        for (double[] row : y) Arrays.setAll(row, k -> data.nextDouble());

        int showEvery = Math.max(hp.epochs() / 10, 1);
        for (int epoch = 1; epoch <= hp.epochs(); epoch++) {
            // sequential stream: trainStep is stateful (must not be parallel)
            double loss = IntStream.range(0, x.length)
                                   .mapToDouble(s -> net.trainStep(x[s], y[s]))
                                   .sum();
            if (epoch % showEvery == 0)
                System.out.printf("epoch %5d  mse = %.6f%n", epoch, loss / x.length);
        }
    }
}
