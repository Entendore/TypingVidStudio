// Program.cs — idiomatic C# 12 / .NET 8: top-level statements, primary
// constructor, extension methods, target-typed new, interpolated formatting.
// Run: dotnet run
//
// HOW IT WORKS
// ------------
// Network: nIn -> nHidden (sigmoid) -> nOut (sigmoid), trained by SGD on MSE.
//
// FORWARD   hidden[j] = Sigmoid(b1[j] + sum_i x[i] * W1[i][j])
//           out[k]    = Sigmoid(b2[k] + sum_j hidden[j] * W2[j][k])
//           Sigmoid(z) = 1 / (1 + Exp(-z))  maps any value into (0,1)
//
// BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
//           dOut[k]    = (out[k] - y[k]) * out[k] * (1 - out[k])
//           dHidden[j] = (sum_k dOut[k] * W2[j][k]) * hidden[j] * (1 - hidden[j])
//
// UPDATE    every gradient = delta * activation feeding that edge:
//           W2[j][k] -= lr * dOut[k] * hidden[j]     b2[k] -= lr * dOut[k]
//           W1[i][j] -= lr * dHidden[j] * x[i]       b1[j] -= lr * dHidden[j]
//
// Replace the "toy dataset" block in the top-level code with real data.

const int nIn = 4, nHidden = 8, nOut = 2;
const double lr = 0.5;
const int epochs = 1000;

NeuralNetwork net = new(nIn, nHidden, nOut, lr, seed: 42);

// Toy dataset — replace with your own.
Random data = new(7);
double[][] x = Enumerable.Range(0, 64)
                         .Select(_ => Enumerable.Range(0, nIn)
                                                .Select(_ => data.NextDouble()).ToArray())
                         .ToArray();
double[][] y = Enumerable.Range(0, 64)
                         .Select(_ => Enumerable.Range(0, nOut)
                                                .Select(_ => data.NextDouble()).ToArray())
                         .ToArray();

int showEvery = Math.Max(epochs / 10, 1);
for (int epoch = 1; epoch <= epochs; epoch++)
{
    // sequential: TrainStep is stateful (must not be parallelized)
    double loss = Enumerable.Range(0, x.Length).Sum(s => net.TrainStep(x[s], y[s]));
    if (epoch % showEvery == 0)
        Console.WriteLine($"epoch {epoch,5}  mse = {loss / x.Length:F6}");
}

/// <summary>One-hidden-layer MLP trained with per-sample SGD.</summary>
internal sealed class NeuralNetwork(int nIn, int nHidden, int nOut, double lr, int seed = 42)
{
    private readonly double[][] _w1 = HeMatrix(nIn, nHidden, new Random(seed));
    private readonly double[][] _w2 = HeMatrix(nHidden, nOut, new Random(seed + 1));
    private readonly double[] _b1 = new double[nHidden];
    private readonly double[] _b2 = new double[nOut];
    private double[] _hidden = new double[nHidden];

    public double[] Forward(double[] input)
    {
        _hidden = new double[nHidden];
        for (int j = 0; j < nHidden; j++)
        {
            double z = _b1[j];
            for (int i = 0; i < nIn; i++) z += input[i] * _w1[i][j];
            _hidden[j] = Sigmoid(z);
        }
        var output = new double[nOut];
        for (int k = 0; k < nOut; k++)
        {
            double z = _b2[k];
            for (int j = 0; j < nHidden; j++) z += _hidden[j] * _w2[j][k];
            output[k] = Sigmoid(z);
        }
        return output;
    }

    /// <summary>One SGD step; returns the sample's squared error.</summary>
    public double TrainStep(double[] input, double[] target)
    {
        double[] output = Forward(input);

        // Output delta: error times sigmoid'(out).
        var dOut = new double[nOut];
        double sqErr = 0.0;
        for (int k = 0; k < nOut; k++)
        {
            double d = output[k] - target[k];
            dOut[k] = d * output[k] * (1.0 - output[k]);
            sqErr += d * d;
        }

        // Hidden delta: backpropagated error times sigmoid'(hidden).
        var dHidden = new double[nHidden];
        for (int j = 0; j < nHidden; j++)
        {
            double back = 0.0;
            for (int k = 0; k < nOut; k++) back += dOut[k] * _w2[j][k];
            dHidden[j] = back * _hidden[j] * (1.0 - _hidden[j]);
        }

        // Gradient descent: weight -= lr * delta * activation on that edge.
        for (int j = 0; j < nHidden; j++)
            for (int k = 0; k < nOut; k++)
                _w2[j][k] -= lr * dOut[k] * _hidden[j];
        for (int k = 0; k < nOut; k++) _b2[k] -= lr * dOut[k];
        for (int i = 0; i < nIn; i++)
            for (int j = 0; j < nHidden; j++)
                _w1[i][j] -= lr * dHidden[j] * input[i];
        for (int j = 0; j < nHidden; j++) _b1[j] -= lr * dHidden[j];
        return sqErr;
    }

    private static double Sigmoid(double x) => 1.0 / (1.0 + Math.Exp(-x));

    private static double[][] HeMatrix(int rows, int cols, Random rng)
    {
        double scale = Math.Sqrt(2.0 / rows);
        return Enumerable.Range(0, rows)
                         .Select(_ => Enumerable.Range(0, cols)
                                                .Select(_ => rng.NextGaussian() * scale).ToArray())
                         .ToArray();
    }
}

internal static class RandomExtensions
{
    /// <summary>Box-Muller standard normal.</summary>
    public static double NextGaussian(this Random rng)
    {
        double u;
        do { u = rng.NextDouble(); } while (u == 0.0);
        return Math.Sqrt(-2.0 * Math.Log(u)) * Math.Cos(2.0 * Math.PI * rng.NextDouble());
    }
}
