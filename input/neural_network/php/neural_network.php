<?php
// neural_network.php — idiomatic PHP 8.2+: constructor property promotion,
// readonly properties, Random\Randomizer with a seeded Xoshiro engine,
// named arguments, arrow functions. Run: php neural_network.php
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
// Replace the "toy dataset" block at the bottom with real data to train on it.

declare(strict_types=1);

final class NeuralNetwork
{
    /** @var array<int, array<int, float>> */
    private array $w1;

    /** @var array<int, float> */
    private array $b1;

    /** @var array<int, array<int, float>> */
    private array $w2;

    /** @var array<int, float> */
    private array $b2;

    /** @var array<int, float> */
    private array $hidden = [];

    public function __construct(
        public readonly int $nIn,
        public readonly int $nHidden,
        public readonly int $nOut,
        public readonly float $lr,
        private \Random\Randomizer $randomizer = new \Random\Randomizer(
            new \Random\Engine\Xoshiro256StarStar(42)
        ),
    ) {
        $this->w1 = $this->heMatrix($this->nIn, $this->nHidden);   // He-style init
        $this->b1 = array_fill(0, $this->nHidden, 0.0);
        $this->w2 = $this->heMatrix($this->nHidden, $this->nOut);
        $this->b2 = array_fill(0, $this->nOut, 0.0);
    }

    /** @return array<int, float> */
    public function forward(array $x): array
    {
        for ($j = 0; $j < $this->nHidden; $j++) {
            $z = $this->b1[$j];
            for ($i = 0; $i < $this->nIn; $i++) {
                $z += $x[$i] * $this->w1[$i][$j];
            }
            $this->hidden[$j] = $this->sigmoid($z);
        }

        $out = [];
        for ($k = 0; $k < $this->nOut; $k++) {
            $z = $this->b2[$k];
            for ($j = 0; $j < $this->nHidden; $j++) {
                $z += $this->hidden[$j] * $this->w2[$j][$k];
            }
            $out[$k] = $this->sigmoid($z);
        }
        return $out;
    }

    /** One SGD step; returns the sample's squared error. */
    public function trainStep(array $x, array $y): float
    {
        $out = $this->forward($x);

        // Output delta: error times sigmoid'(out).
        $dOut = [];
        $sqErr = 0.0;
        for ($k = 0; $k < $this->nOut; $k++) {
            $delta = $out[$k] - $y[$k];
            $dOut[$k] = $delta * $out[$k] * (1.0 - $out[$k]);
            $sqErr += $delta * $delta;
        }

        // Hidden delta: backpropagated error times sigmoid'(hidden).
        $dHidden = [];
        for ($j = 0; $j < $this->nHidden; $j++) {
            $back = 0.0;
            for ($k = 0; $k < $this->nOut; $k++) {
                $back += $dOut[$k] * $this->w2[$j][$k];
            }
            $a = $this->hidden[$j];
            $dHidden[$j] = $back * $a * (1.0 - $a);
        }

        // Gradient descent: weight -= lr * delta * activation on that edge.
        foreach ($dHidden as $j => $dh) {
            foreach ($dOut as $k => $do) {
                $this->w2[$j][$k] -= $this->lr * $do * $this->hidden[$j];
            }
        }
        foreach ($dOut as $k => $do) {
            $this->b2[$k] -= $this->lr * $do;
        }
        foreach ($x as $i => $xi) {
            foreach ($dHidden as $j => $dh) {
                $this->w1[$i][$j] -= $this->lr * $dh * $xi;
            }
        }
        foreach ($dHidden as $j => $dh) {
            $this->b1[$j] -= $this->lr * $dh;
        }
        return $sqErr;
    }

    private function heMatrix(int $rows, int $cols): array
    {
        $scale = sqrt(2.0 / $rows);
        $matrix = [];
        for ($i = 0; $i < $rows; $i++) {
            for ($j = 0; $j < $cols; $j++) {
                $matrix[$i][$j] = $this->gauss() * $scale;
            }
        }
        return $matrix;
    }

    /** Box-Muller standard normal on top of Random\Randomizer. */
    private function gauss(): float
    {
        do {
            $u = $this->randomizer->getFloat();
        } while ($u === 0.0);
        return sqrt(-2.0 * log($u)) * cos(2.0 * M_PI * $this->randomizer->getFloat());
    }

    private function sigmoid(float $x): float
    {
        return 1.0 / (1.0 + exp(-$x));
    }
}

// ---- demo (replace with your own data) ------------------------------
const N_IN = 4;
const N_HIDDEN = 8;
const N_OUT = 2;
const LEARNING_RATE = 0.5;
const EPOCHS = 1000;

 $nn = new NeuralNetwork(
    nIn: N_IN,
    nHidden: N_HIDDEN,
    nOut: N_OUT,
    lr: LEARNING_RATE,
);

 $data = new \Random\Randomizer(new \Random\Engine\Xoshiro256StarStar(7));
 $dataset = [];
for ($s = 0; $s < 64; $s++) {
    $dataset[] = [
        'x' => array_map(fn (): float => $data->getFloat(), range(1, N_IN)),
        'y' => array_map(fn (): float => $data->getFloat(), range(1, N_OUT)),
    ];
}

 $showEvery = max(intdiv(EPOCHS, 10), 1);
for ($epoch = 1; $epoch <= EPOCHS; $epoch++) {
    $loss = array_sum(array_map(
        static fn (array $sample): float => $nn->trainStep($sample['x'], $sample['y']),
        $dataset,
    ));
    if ($epoch % $showEvery === 0) {
        printf("epoch %5d  mse = %.6f\n", $epoch, $loss / count($dataset));
    }
}
