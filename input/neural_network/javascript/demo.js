// demo.js — entry point. Run: node demo.js
import { NeuralNetwork } from "./neural_network.js";

const hyper = { nIn: 4, nHidden: 8, nOut: 2, lr: 0.5 };
const epochs = 1000;
const nn = new NeuralNetwork(hyper);

// Toy dataset — replace with your own.
const dataset = Array.from({ length: 64 }, () => ({
  x: Array.from({ length: hyper.nIn }, () => Math.random()),
  y: Array.from({ length: hyper.nOut }, () => Math.random()),
}));

const showEvery = Math.max(Math.floor(epochs / 10), 1);
for (let epoch = 1; epoch <= epochs; epoch++) {
  const loss = dataset.reduce((sum, { x, y }) => sum + nn.trainStep(x, y), 0);
  if (epoch % showEvery === 0) {
    console.log(`epoch ${String(epoch).padStart(5)}  mse = ${(loss / dataset.length).toFixed(6)}`);
  }
}
