# neural_network.ps1 — idiomatic PowerShell: a PS class with hidden members,
# Set-StrictMode, pipeline + Measure-Object reduction, -f format operator,
# [pscustomobject] config. Run: pwsh ./neural_network.ps1   (PS 5.1+ / 7)
#
# HOW IT WORKS
# ------------
# Network: NIn -> NHidden (sigmoid) -> NOut (sigmoid), trained by SGD on MSE.
#
# FORWARD   hidden[j] = Sigmoid(B1[j] + sum_i x[i] * W1[i][j])
#           out[k]    = Sigmoid(B2[k] + sum_j hidden[j] * W2[j][k])
#           Sigmoid(z) = 1 / (1 + Exp(-z))  maps any value into (0,1)
#
# BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
#           dOut[k]    = (out[k] - y[k]) * out[k] * (1 - out[k])
#           dHidden[j] = (sum_k dOut[k] * W2[j][k]) * hidden[j] * (1 - hidden[j])
#
# UPDATE    every gradient = delta * activation feeding that edge:
#           W2[j][k] -= lr * dOut[k] * hidden[j]     B2[k] -= lr * dOut[k]
#           W1[i][j] -= lr * dHidden[j] * x[i]       B1[j] -= lr * dHidden[j]
#
# Replace the "toy dataset" block at the bottom with real data to train on it.

#Requires -Version 5.1
Set-StrictMode -Version Latest

<#
.SYNOPSIS
    One-hidden-layer MLP with sigmoid activations, trained with SGD.
#>
class NeuralNetwork {
    hidden [double] $LearningRate
    hidden [int] $NIn
    hidden [int] $NHidden
    hidden [int] $NOut
    hidden [double[][]] $W1
    hidden [double[]] $B1
    hidden [double[][]] $W2
    hidden [double[]] $B2
    hidden [double[]] $Hidden

    NeuralNetwork([int] $nIn, [int] $nHidden, [int] $nOut, [double] $lr, [int] $seed = 42) {
        if ($nIn -lt 1 -or $nHidden -lt 1 -or $nOut -lt 1 -or $lr -le 0) {
            throw 'layer sizes must be positive and lr must be > 0'
        }
        $this.NIn = $nIn; $this.NHidden = $nHidden; $this.NOut = $nOut
        $this.LearningRate = $lr
        $rng = [System.Random]::new($seed)
        $this.W1 = [NeuralNetwork]::HeMatrix($nIn, $nHidden, $rng)   # He-style init
        $this.B1 = [double[]]::new($nHidden)
        $this.W2 = [NeuralNetwork]::HeMatrix($nHidden, $nOut, $rng)
        $this.B2 = [double[]]::new($nOut)
        $this.Hidden = [double[]]::new($nHidden)
    }

    hidden static [double[]] GaussVector([int] $count, [double] $scale, [System.Random] $rng) {
        $v = [double[]]::new($count)
        for ($i = 0; $i -lt $count; $i++) {
            do { $u = $rng.NextDouble() } while ($u -eq 0.0)
            $v[$i] = [Math]::Sqrt(-2.0 * [Math]::Log($u)) *
                     [Math]::Cos(2.0 * [Math]::PI * $rng.NextDouble()) * $scale
        }
        return $v
    }

    hidden static [double[][]] HeMatrix([int] $rows, [int] $cols, [System.Random] $rng) {
        $m = [double[][]]::new($rows)
        for ($i = 0; $i -lt $rows; $i++) {
            $m[$i] = [NeuralNetwork]::GaussVector($cols, [Math]::Sqrt(2.0 / $rows), $rng)
        }
        return $m
    }

    [double[]] Forward([double[]] $x) {
        for ($j = 0; $j -lt $this.NHidden; $j++) {
            $z = $this.B1[$j]
            for ($i = 0; $i -lt $this.NIn; $i++) { $z += $x[$i] * $this.W1[$i][$j] }
            $this.Hidden[$j] = 1.0 / (1.0 + [Math]::Exp(-$z))
        }
        $out = [double[]]::new($this.NOut)
        for ($k = 0; $k -lt $this.NOut; $k++) {
            $z = $this.B2[$k]
            for ($j = 0; $j -lt $this.NHidden; $j++) { $z += $this.Hidden[$j] * $this.W2[$j][$k] }
            $out[$k] = 1.0 / (1.0 + [Math]::Exp(-$z))
        }
        return $out
    }

    [double] TrainStep([double[]] $x, [double[]] $y) {
        $out = $this.Forward($x)
        # Output delta: error times sigmoid'(out).
        $dOut = [double[]]::new($this.NOut)
        $sqErr = 0.0
        for ($k = 0; $k -lt $this.NOut; $k++) {
            $d = $out[$k] - $y[$k]
            $dOut[$k] = $d * $out[$k] * (1.0 - $out[$k])
            $sqErr += $d * $d
        }
        # Hidden delta: backpropagated error times sigmoid'(hidden).
        $dHidden = [double[]]::new($this.NHidden)
        for ($j = 0; $j -lt $this.NHidden; $j++) {
            $back = 0.0
            for ($k = 0; $k -lt $this.NOut; $k++) { $back += $dOut[$k] * $this.W2[$j][$k] }
            $dHidden[$j] = $back * $this.Hidden[$j] * (1.0 - $this.Hidden[$j])
        }
        # Gradient descent: weight -= lr * delta * activation on that edge.
        for ($j = 0; $j -lt $this.NHidden; $j++) {
            for ($k = 0; $k -lt $this.NOut; $k++) {
                $this.W2[$j][$k] -= $this.LearningRate * $dOut[$k] * $this.Hidden[$j]
            }
        }
        for ($k = 0; $k -lt $this.NOut; $k++) { $this.B2[$k] -= $this.LearningRate * $dOut[$k] }
        for ($i = 0; $i -lt $this.NIn; $i++) {
            for ($j = 0; $j -lt $this.NHidden; $j++) {
                $this.W1[$i][$j] -= $this.LearningRate * $dHidden[$j] * $x[$i]
            }
        }
        for ($j = 0; $j -lt $this.NHidden; $j++) { $this.B1[$j] -= $this.LearningRate * $dHidden[$j] }
        return $sqErr
    }
}

# ---- demo (replace with your own data) --------------------------------
 $hyper = [pscustomobject]@{
    NIn     = 4
    NHidden = 8
    NOut    = 2
    Lr      = 0.5
}
 $epochs = 1000

 $net = [NeuralNetwork]::new($hyper.NIn, $hyper.NHidden, $hyper.NOut, $hyper.Lr)

 $rng = [System.Random]::new(7)
 $dataset = 1..64 | ForEach-Object {
    [pscustomobject]@{
        X = 1..$hyper.NIn  | ForEach-Object { $rng.NextDouble() }
        Y = 1..$hyper.NOut | ForEach-Object { $rng.NextDouble() }
    }
}

 $showEvery = [Math]::Max([int]($epochs / 10), 1)
foreach ($epoch in 1..$epochs) {
    # Pipeline: train every sample, then reduce the errors with Measure-Object.
    $loss = $dataset |
        ForEach-Object { $net.TrainStep($_.X, $_.Y) } |
        Measure-Object -Sum |
        Select-Object -ExpandProperty Sum

    if ($epoch % $showEvery -eq 0) {
        '{0,5}  mse = {1:F6}' -f $epoch, ($loss / $dataset.Count)
    }
}
