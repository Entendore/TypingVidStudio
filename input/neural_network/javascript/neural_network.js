// neural_network.js — idiomatic modern JS: ES module, #private fields,
// Float64Array storage, injectable RNG. Library module; see demo.js.
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
// Weights live in flat row-major Float64Arrays: W[i][j] === W[i*nCols + j].

export const sigmoid = (x) => 1 / (1 + Math.exp(-x));

/** Box-Muller transform on top of an injectable uniform source. */
export function gaussian(random = Math.random) {
  let u = random();
  while (u === 0) u = random();
  const v = random();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

/** He-initialised weight matrix, flat and row-major. */
export function heMatrix(rows, cols, random = Math.random) {
  const scale = Math.sqrt(2 / rows);
  const w = new Float64Array(rows * cols);
  for (let i = 0; i < w.length; i++) w[i] = gaussian(random) * scale;
  return w;
}

export class NeuralNetwork {
  #lr;
  #nIn;
  #nHidden;
  #nOut;
  #w1;
  #b1;
  #w2;
  #b2;
  #hidden;

  constructor({ nIn, nHidden, nOut, lr }, random = Math.random) {
    this.#nIn = nIn;
    this.#nHidden = nHidden;
    this.#nOut = nOut;
    this.#lr = lr;
    this.#w1 = heMatrix(nIn, nHidden, random);
    this.#b1 = new Float64Array(nHidden);
    this.#w2 = heMatrix(nHidden, nOut, random);
    this.#b2 = new Float64Array(nOut);
    this.#hidden = new Float64Array(nHidden);
  }

  forward(x) {
    const nIn = this.#nIn, nHid = this.#nHidden, nOut = this.#nOut;
    const w1 = this.#w1, b1 = this.#b1, hidden = this.#hidden;
    for (let j = 0; j < nHid; j++) {
      let z = b1[j];
      for (let i = 0; i < nIn; i++) z += x[i] * w1[i * nHid + j];
      hidden[j] = sigmoid(z);
    }
    const w2 = this.#w2, b2 = this.#b2;
    const out = new Float64Array(nOut);
    for (let k = 0; k < nOut; k++) {
      let z = b2[k];
      for (let j = 0; j < nHid; j++) z += hidden[j] * w2[j * nOut + k];
      out[k] = sigmoid(z);
    }
    return out;
  }

  trainStep(x, y) {
    const lr = this.#lr;
    const out = this.forward(x);

    // Output delta: error * sigmoid'(out)
    const dOut = new Float64Array(this.#nOut);
    let sqErr = 0;
    for (let k = 0; k < this.#nOut; k++) {
      const d = out[k] - y[k];
      dOut[k] = d * out[k] * (1 - out[k]);
      sqErr += d * d;
    }

    // Hidden delta: backpropagated error * sigmoid'(hidden)
    const dHidden = new Float64Array(this.#nHidden);
    const hidden = this.#hidden, w2 = this.#w2;
    for (let j = 0; j < this.#nHidden; j++) {
      let back = 0;
      for (let k = 0; k < this.#nOut; k++) back += dOut[k] * w2[j * this.#nOut + k];
      dHidden[j] = back * hidden[j] * (1 - hidden[j]);
    }

    // Gradient descent updates
    for (let j = 0; j < this.#nHidden; j++)
      for (let k = 0; k < this.#nOut; k++)
        w2[j * this.#nOut + k] -= lr * dOut[k] * hidden[j];
    for (let k = 0; k < this.#nOut; k++) this.#b2[k] -= lr * dOut[k];
    const w1 = this.#w1;
    for (let i = 0; i < this.#nIn; i++)
      for (let j = 0; j < this.#nHidden; j++)
        w1[i * this.#nHidden + j] -= lr * dHidden[j] * x[i];
    for (let j = 0; j < this.#nHidden; j++) this.#b1[j] -= lr * dHidden[j];
    return sqErr;
  }
}
