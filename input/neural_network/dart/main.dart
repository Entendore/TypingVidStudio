// main.dart — idiomatic Dart 3: `final class`, records with named fields and
// destructuring patterns, `.indexed` iteration, extension methods.
// Run: dart run main.dart
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

import 'dart:math';

extension Gaussian on Random {
  /// Box-Muller standard normal.
  double nextGaussian() {
    var u = 0.0;
    while (u == 0.0) {
      u = nextDouble();
    }
    return sqrt(-2 * log(u)) * cos(2 * pi * nextDouble());
  }
}

double sigmoid(double x) => 1 / (1 + exp(-x));

/// One-hidden-layer MLP. `final class` forbids extends/implements outside
/// this library — the intended contract for concrete data structures.
final class NeuralNetwork {
  final double lr;
  final int nIn, nHidden, nOut;
  late final List<List<double>> w1;
  late final List<double> b1;
  late final List<List<double>> w2;
  late final List<double> b2;

  NeuralNetwork({
    required this.nIn,
    required this.nHidden,
    required this.nOut,
    required this.lr,
    int seed = 42,
  }) {
    final rng = Random(seed);
    w1 = _heMatrix(nIn, nHidden, rng);      // He-style init
    b1 = List.filled(nHidden, 0.0);
    w2 = _heMatrix(nHidden, nOut, rng);
    b2 = List.filled(nOut, 0.0);
  }

  static List<List<double>> _heMatrix(int rows, int cols, Random rng) {
    final scale = sqrt(2.0 / rows);
    return List.generate(
      rows,
      (_) => List.generate(cols, (_) => rng.nextGaussian() * scale, growable: false),
      growable: false,
    );
  }

  static double _dot(List<double> a, List<double> b) {
    var sum = 0.0;
    for (var i = 0; i < a.length; i++) {
      sum += a[i] * b[i];
    }
    return sum;
  }

  /// Forward pass; returns both activations as a named record.
  ({List<double> hidden, List<double> output}) _forwardWithCache(List<double> x) {
    final hidden = List.generate(
      nHidden,
      (j) => sigmoid(b1[j] + _dot(x, [for (final row in w1) row[j]])),
      growable: false,
    );
    final output = List.generate(
      nOut,
      (k) => sigmoid(b2[k] + _dot(hidden, [for (final row in w2) row[k]])),
      growable: false,
    );
    return (hidden: hidden, output: output);
  }

  List<double> forward(List<double> x) => _forwardWithCache(x).output;

  /// One SGD step; returns the sample's squared error.
  double trainStep(List<double> x, List<double> y) {
    final (:hidden, :output) = _forwardWithCache(x);   // record destructuring

    // Output delta: error times sigmoid'(out).
    final dOut = [
      for (final (k, o) in output.indexed) (o - y[k]) * o * (1 - o),
    ];
    // Hidden delta: backpropagated error times sigmoid'(hidden).
    final dHidden = [
      for (final (j, h) in hidden.indexed)
        _dot(dOut, [for (final row in w2) row[j]]) * h * (1 - h),
    ];

    // Gradient descent: weight -= lr * delta * activation on that edge.
    for (var j = 0; j < nHidden; j++) {
      for (var k = 0; k < nOut; k++) {
        w2[j][k] -= lr * dOut[k] * hidden[j];
      }
      b1[j] -= lr * dHidden[j];
    }
    for (var k = 0; k < nOut; k++) {
      b2[k] -= lr * dOut[k];
    }
    for (var i = 0; i < nIn; i++) {
      for (var j = 0; j < nHidden; j++) {
        w1[i][j] -= lr * dHidden[j] * x[i];
      }
    }

    var sqErr = 0.0;
    for (final (k, o) in output.indexed) {
      sqErr += (o - y[k]) * (o - y[k]);
    }
    return sqErr;
  }
}

void main() {
  const nIn = 4;
  const nHidden = 8;
  const nOut = 2;
  const lr = 0.5;
  const epochs = 1000;

  final net = NeuralNetwork(nIn: nIn, nHidden: nHidden, nOut: nOut, lr: lr);

  // Toy dataset — replace with your own.
  final rng = Random(7);
  final dataset = List.generate(
    64,
    (_) => (
      x: List.generate(nIn, (_) => rng.nextDouble(), growable: false),
      y: List.generate(nOut, (_) => rng.nextDouble(), growable: false),
    ),
    growable: false,
  );

  final showEvery = max(epochs ~/ 10, 1);
  for (var epoch = 1; epoch <= epochs; epoch++) {
    final loss = dataset.fold<double>(0, (sum, s) => sum + net.trainStep(s.x, s.y));
    if (epoch % showEvery == 0) {
      print('epoch ${epoch.toString().padLeft(5)}  '
          'mse = ${(loss / dataset.length).toStringAsFixed(6)}');
    }
  }
}
