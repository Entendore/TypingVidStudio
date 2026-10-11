#!/usr/bin/env perl
# neural_network.pl — idiomatic modern core Perl: `use v5.36` enables strict,
# warnings and signatures; List::Util for reductions; block package.
# Run: perl neural_network.pl   (Perl 5.36+)
#
# HOW IT WORKS
# ------------
# Network: n_in -> n_hidden (sigmoid) -> n_out (sigmoid), trained by SGD
# on mean squared error.
#
# FORWARD   hidden[j] = sigmoid(b1[j] + sum_i x[i] * w1[i][j])
#           out[k]    = sigmoid(b2[k] + sum_j hidden[j] * w2[j][k])
#           sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)
#
# BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
#           d_out[k]    = (out[k] - y[k]) * out[k] * (1 - out[k])
#           d_hidden[j] = (sum_k d_out[k] * w2[j][k]) * hidden[j] * (1 - hidden[j])
#
# UPDATE    every gradient = delta * activation feeding that edge:
#           w2[j][k] -= lr * d_out[k] * hidden[j]    b2[k] -= lr * d_out[k]
#           w1[i][j] -= lr * d_hidden[j] * x[i]      b1[j] -= lr * d_hidden[j]
#
# Replace the "toy dataset" block at the bottom with real data to train on it.

use v5.36;

package NeuralNetwork {

    use List::Util qw(sum0);

    use constant PI => 4 * atan2(1, 1);

    sub sigmoid ($x) { 1.0 / (1.0 + exp(-$x)) }

    # Box-Muller standard normal (core Perl ships no gaussian).
    sub gauss () {
        my $u = rand;
        $u = rand while $u == 0.0;
        sqrt(-2.0 * log($u)) * cos(2.0 * PI * rand)
    }

    # He-style init: N(0, sqrt(2/rows)).
    sub he_matrix ($rows, $cols) {
        my $scale = sqrt(2.0 / $rows);
        [ map { [ map { gauss() * $scale } 1 .. $cols ] } 1 .. $rows ]
    }

    sub new ($class, %arg) {
        my $self = bless {
            n_in     => $arg{n_in},
            n_hidden => $arg{n_hidden},
            n_out    => $arg{n_out},
            lr       => $arg{lr},
            b1       => [ map { 0.0 } 1 .. $arg{n_hidden} ],
            b2       => [ map { 0.0 } 1 .. $arg{n_out} ],
            hidden   => [],
        }, $class;
        $self->{w1} = he_matrix($arg{n_in},     $arg{n_hidden});
        $self->{w2} = he_matrix($arg{n_hidden}, $arg{n_out});
        return $self;
    }

    sub forward ($self, $x) {
        my ($n_in, $n_hid, $n_out) = @{$self}{qw(n_in n_hidden n_out)};

        $self->{hidden} = [
            map {
                my $j = $_;
                sigmoid(
                    $self->{b1}[$j]
                  + sum0 map { $x->[$_] * $self->{w1}[$_][$j] } 0 .. $n_in - 1
                )
            } 0 .. $n_hid - 1
        ];

        return [
            map {
                my $k = $_;
                sigmoid(
                    $self->{b2}[$k]
                  + sum0 map { $self->{hidden}[$_] * $self->{w2}[$_][$k] } 0 .. $n_hid - 1
                )
            } 0 .. $n_out - 1
        ];
    }

    sub train_step ($self, $x, $y) {
        my $out = $self->forward($x);
        my ($n_in, $n_hid, $n_out, $lr) = @{$self}{qw(n_in n_hidden n_out lr)};

        # Output delta: error times sigmoid'(out).
        my @d_out = map {
            ($out->[$_] - $y->[$_]) * $out->[$_] * (1.0 - $out->[$_])
        } 0 .. $n_out - 1;
        my $sq_err = sum0 map {
            my $d = $out->[$_] - $y->[$_];
            $d * $d;
        } 0 .. $n_out - 1;

        # Hidden delta: backpropagated error times sigmoid'(hidden).
        my @d_hidden = map {
            my $j = $_;
            my $a = $self->{hidden}[$j];
            (sum0 map { $d_out[$_] * $self->{w2}[$j][$_] } 0 .. $n_out - 1) * $a * (1.0 - $a);
        } 0 .. $n_hid - 1;

        # Gradient descent: weight -= lr * delta * activation on that edge.
        for my $j (0 .. $n_hid - 1) {
            $self->{w2}[$j][$_] -= $lr * $d_out[$_] * $self->{hidden}[$j] for 0 .. $n_out - 1;
        }
        $self->{b2}[$_] -= $lr * $d_out[$_] for 0 .. $n_out - 1;
        for my $i (0 .. $n_in - 1) {
            $self->{w1}[$i][$_] -= $lr * $d_hidden[$_] * $x->[$i] for 0 .. $n_hid - 1;
        }
        $self->{b1}[$_] -= $lr * $d_hidden[$_] for 0 .. $n_hid - 1;

        return $sq_err;
    }
}

# ---- demo (replace with your own data) ------------------------------
srand(42);

my $nn = NeuralNetwork->new(
    n_in     => 4,
    n_hidden => 8,
    n_out    => 2,
    lr       => 0.5,
);

my ($N_IN, $N_OUT) = (4, 2);
my ($epochs, $show_every) = (1000, int(1000 / 10) || 1);

my (@x, @y);
for my $s (0 .. 63) {
    $x[$s] = [ map { rand() } 1 .. $N_IN ];
    $y[$s] = [ map { rand() } 1 .. $N_OUT ];
}

for my $epoch (1 .. $epochs) {
    my $loss = sum0 map { $nn->train_step($x[$_], $y[$_]) } 0 .. 63;
    printf "epoch %5d  mse = %.6f\n", $epoch, $loss / 64
        if $epoch % $show_every == 0;
}
