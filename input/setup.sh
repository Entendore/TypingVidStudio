#!/usr/bin/env bash
#
# generate_nn.sh — Generate a custom neural network project in a directory.
#
# Each generated file is self-contained and documented: a "HOW IT WORKS"
# comment block explains the network (forward pass, backprop, SGD update)
# in the language's own comment syntax.
#
# Usage:
#   ./generate_nn.sh [options] [language ...]
#
# Languages:
#   python cpp c java javascript typescript go rust ruby kotlin swift
#   csharp dart php perl lua haskell r julia scala fsharp nim zig ocaml
#   elixir groovy objectivec fortran powershell          (or: all)
#
# Options:
#   -d, --dir PATH     Output directory (default: ./neural_network)
#       --input N      Input layer neurons   (default: 4)
#       --hidden N     Hidden layer neurons  (default: 8)
#       --output N     Output layer neurons  (default: 2)
#       --lr FLOAT     Learning rate         (default: 0.5)
#       --epochs N     Demo training epochs  (default: 1000)
#       --list         List supported languages and exit
#   -h, --help         Show this help
#
# Examples:
#   ./generate_nn.sh                        # interactive menu
#   ./generate_nn.sh all                    # every language
#   ./generate_nn.sh python rust zig --hidden 16 --lr 0.3

set -euo pipefail

# ---------------------------------------------------------------- defaults
OUTPUT_DIR="neural_network"
INPUT_SIZE=4
HIDDEN_SIZE=8
OUTPUT_SIZE=2
LEARNING_RATE="0.5"
EPOCHS=1000

readonly -a SUPPORTED=(python cpp c java javascript typescript go rust ruby
                       kotlin swift csharp dart php perl lua haskell r julia
                       scala fsharp nim zig ocaml elixir groovy objectivec
                       fortran powershell)

# ---------------------------------------------------------------- colors
if [[ -t 1 ]]; then
    C_RED=$'\033[0;31m'; C_GRN=$'\033[0;32m'; C_YEL=$'\033[1;33m'
    C_BLU=$'\033[0;34m'; C_OFF=$'\033[0m'
else
    C_RED=""; C_GRN=""; C_YEL=""; C_BLU=""; C_OFF=""
fi

info() { printf '%s[INFO]%s %s\n' "$C_BLU" "$C_OFF" "$1"; }
ok()   { printf '%s[ OK ]%s %s\n' "$C_GRN" "$C_OFF" "$1"; }
warn() { printf '%s[WARN]%s %s\n' "$C_YEL" "$C_OFF" "$1"; }
die()  { printf '%s[ERR ]%s %s\n' "$C_RED" "$C_OFF" "$1" >&2; exit 1; }

CREATED=()
add_file() { CREATED+=("$1"); ok "created $1"; }

# ---------------------------------------------------------------- help/list
usage() {
    cat <<'EOF'
generate_nn.sh — Generate a documented custom neural network in a directory.

Usage:
  ./generate_nn.sh [options] [language ...]

Languages:
  python, cpp, c, java, javascript, typescript, go, rust, ruby, kotlin,
  swift, csharp, dart, php, perl, lua, haskell, r, julia, scala, fsharp,
  nim, zig, ocaml, elixir, groovy, objectivec, fortran, powershell  (or: all)

Options:
  -d, --dir PATH     Output directory (default: ./neural_network)
      --input N      Input layer neurons   (default: 4)
      --hidden N     Hidden layer neurons  (default: 8)
      --output N     Output layer neurons  (default: 2)
      --lr FLOAT     Learning rate         (default: 0.5)
      --epochs N     Demo training epochs  (default: 1000)
      --list         List supported languages
  -h, --help         Show this help
EOF
}

list_languages() {
    echo "Supported languages:"
    local lang
    for lang in "${SUPPORTED[@]}"; do
        echo "  - $lang"
    done
}

# ---------------------------------------------------------------- parsing
parse_args() {
    SELECTED=()
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -d|--dir)
                [[ $# -ge 2 ]] || die "--dir requires a path"
                OUTPUT_DIR="$2"; shift 2 ;;
            --input|--hidden|--output|--epochs)
                [[ $# -ge 2 ]] || die "$1 requires a value"
                [[ "$2" =~ ^[0-9]+$ ]] || die "$1 expects a positive integer, got '$2'"
                [[ "$2" -ge 1 ]] || die "$1 must be >= 1"
                case "$1" in
                    --input)  INPUT_SIZE="$2" ;;
                    --hidden) HIDDEN_SIZE="$2" ;;
                    --output) OUTPUT_SIZE="$2" ;;
                    --epochs) EPOCHS="$2" ;;
                esac
                shift 2 ;;
            --lr)
                [[ $# -ge 2 ]] || die "--lr requires a value"
                [[ "$2" =~ ^[0-9]*\.?[0-9]+$ ]] || die "--lr expects a number, got '$2'"
                LEARNING_RATE="$2"; shift 2 ;;
            --list)  list_languages; exit 0 ;;
            -h|--help) usage; exit 0 ;;
            -*) die "Unknown option: $1 (try --help)" ;;
            *)  SELECTED+=("$1"); shift ;;
        esac
    done
}

interactive_menu() {
    echo
    echo "Languages available:"
    local i=1 lang
    for lang in "${SUPPORTED[@]}"; do
        printf "  %2d) %s\n" "$i" "$lang"
        i=$((i + 1))
    done
    printf "   a) all of the above\n"
    printf "\nSelect (e.g. '1 3', 'python go', or 'a'): "
    local answer
    read -r answer
    [[ -z "$answer" ]] && die "No selection made."

    local token
    for token in ${answer//,/ }; do
        if [[ "$token" == "a" || "$token" == "all" ]]; then
            SELECTED=("${SUPPORTED[@]}")
            return
        fi
        if [[ "$token" =~ ^[0-9]+$ ]]; then
            if (( token < 1 || token > ${#SUPPORTED[@]} )); then
                die "Invalid choice: $token"
            fi
            SELECTED+=("${SUPPORTED[$((token - 1))]}")
        else
            SELECTED+=("$token")
        fi
    done
}

valid_lang() {
    local candidate="$1" s
    for s in "${SUPPORTED[@]}"; do
        [[ "$candidate" == "$s" ]] && return 0
    done
    return 1
}

resolve_langs() {
    if [[ " ${SELECTED[*]} " == *" all "* ]]; then
        LANGS=("${SUPPORTED[@]}")
        return
    fi

    LANGS=()
    local seen=" " raw lang
    for raw in "${SELECTED[@]}"; do
        lang="$(printf '%s' "$raw" | tr '[:upper:]' '[:lower:]')"
        case "$lang" in
            js)      lang="javascript" ;;
            ts)      lang="typescript" ;;
            c++)     lang="cpp" ;;
            golang)  lang="go" ;;
            kt)      lang="kotlin" ;;
            cs|dotnet) lang="csharp" ;;
            hs)      lang="haskell" ;;
            pl)      lang="perl" ;;
            fs)      lang="fsharp" ;;
            ex|exs)  lang="elixir" ;;
            ml)      lang="ocaml" ;;
            objc|obj-c|objective-c) lang="objectivec" ;;
            f90)     lang="fortran" ;;
            ps|ps1|pwsh) lang="powershell" ;;
        esac
        valid_lang "$lang" || die "Unsupported language: '$raw' (run with --list)"
        if [[ "$seen" != *" $lang "* ]]; then
            seen+="$lang "
            LANGS+=("$lang")
        fi
    done
}

# Substitute config placeholders inside generated files (portable sed).
fill_placeholders() {
    local file="$1"
    sed -e "s/__INPUT__/${INPUT_SIZE}/g" \
        -e "s/__HIDDEN__/${HIDDEN_SIZE}/g" \
        -e "s/__OUTPUT__/${OUTPUT_SIZE}/g" \
        -e "s/__LR__/${LEARNING_RATE}/g" \
        -e "s/__EPOCHS__/${EPOCHS}/g" \
        "$file" > "${file}.tmp" && mv "${file}.tmp" "$file"
}

# ============================================================ generators

gen_python() {
    mkdir -p "$OUTPUT_DIR/python"
    local f="$OUTPUT_DIR/python/neural_network.py"
    cat > "$f" <<'EOF'
#!/usr/bin/env python3
"""One-hidden-layer MLP — idiomatic NumPy (Generator API, dataclass, type hints).

HOW IT WORKS
------------
Network: n_in -> n_hidden (sigmoid) -> n_out (sigmoid), trained by SGD
on mean squared error.

FORWARD   hidden[j] = sigmoid(b1[j] + sum_i x[i] * W1[i][j])
          out[k]    = sigmoid(b2[k] + sum_j hidden[j] * W2[j][k])
          sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)

BACKPROP  (chain rule; the derivative of sigmoid at output a is a*(1-a)):
          dOut[k]    = (out[k] - y[k]) * out[k] * (1 - out[k])
          dHidden[j] = (sum_k dOut[k] * W2[j][k]) * hidden[j] * (1 - hidden[j])

UPDATE    every gradient = delta * activation feeding that edge:
          W2[j][k] -= lr * dOut[k] * hidden[j]     b2[k] -= lr * dOut[k]
          W1[i][j] -= lr * dHidden[j] * x[i]       b1[j] -= lr * dHidden[j]

Replace the "toy dataset" block in main() with real data to train on it.
Run: python neural_network.py   (requires: pip install numpy)
"""

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

Array = npt.NDArray[np.float64]


def sigmoid(x: Array) -> Array:
    return 1.0 / (1.0 + np.exp(-x))


@dataclass(frozen=True)
class Config:
    """Hyperparameters, validated on construction."""

    n_in: int
    n_hidden: int
    n_out: int
    lr: float

    def __post_init__(self) -> None:
        if min(self.n_in, self.n_hidden, self.n_out) < 1:
            raise ValueError("layer sizes must be positive")
        if self.lr <= 0.0:
            raise ValueError("learning rate must be positive")


class NeuralNetwork:
    def __init__(self, cfg: Config, *, seed: int = 42) -> None:
        self.cfg = cfg
        rng = np.random.default_rng(seed)  # modern Generator API
        # He-style init: variance scaled by fan-in so activations stay healthy.
        self.w1 = rng.standard_normal((cfg.n_in, cfg.n_hidden)) * np.sqrt(2 / cfg.n_in)
        self.b1 = np.zeros(cfg.n_hidden)
        self.w2 = rng.standard_normal((cfg.n_hidden, cfg.n_out)) * np.sqrt(2 / cfg.n_hidden)
        self.b2 = np.zeros(cfg.n_out)
        self.a1: Array | None = None

    def forward(self, x: Array) -> Array:
        self.a1 = sigmoid(x @ self.w1 + self.b1)          # layer 1
        return sigmoid(self.a1 @ self.w2 + self.b2)       # layer 2

    def sgd_step(self, x: Array, y: Array) -> float:
        """One full-batch gradient step; returns the batch MSE."""
        out = self.forward(x)
        n = x.shape[0]

        # Backprop: error signal flows output -> hidden via W2.T
        delta2 = (out - y) * out * (1.0 - out)            # sigmoid'(out) factored in
        delta1 = (delta2 @ self.w2.T) * self.a1 * (1.0 - self.a1)

        # Gradients are delta (next layer) x activation (this layer)
        self.w2 -= self.cfg.lr * (self.a1.T @ delta2) / n
        self.b2 -= self.cfg.lr * delta2.mean(axis=0)
        self.w1 -= self.cfg.lr * (x.T @ delta1) / n
        self.b1 -= self.cfg.lr * delta1.mean(axis=0)
        return float(np.mean((out - y) ** 2))


def train(net: NeuralNetwork, x: Array, y: Array, epochs: int) -> list[float]:
    history: list[float] = []
    for epoch in range(1, epochs + 1):
        mse = net.sgd_step(x, y)
        history.append(mse)
        if epoch % max(epochs // 10, 1) == 0:
            print(f"epoch {epoch:5d}  mse = {mse:.6f}")
    return history


def main() -> None:
    cfg = Config(n_in=__INPUT__, n_hidden=__HIDDEN__, n_out=__OUTPUT__, lr=__LR__)
    rng = np.random.default_rng(7)  # toy data — replace with your own
    x = rng.random((64, cfg.n_in))
    y = rng.random((64, cfg.n_out))

    net = NeuralNetwork(cfg)
    history = train(net, x, y, epochs=__EPOCHS__)
    print(f"\nfinal mse = {history[-1]:.6f}")
    print(np.round(net.forward(x[:5]), 3))


if __name__ == "__main__":
    main()
EOF
    fill_placeholders "$f"
    chmod +x "$f"
    cat > "$OUTPUT_DIR/python/requirements.txt" <<'EOF'
numpy>=1.24
EOF
    add_file "$OUTPUT_DIR/python/neural_network.py"
    add_file "$OUTPUT_DIR/python/requirements.txt"
}

gen_cpp() {
    mkdir -p "$OUTPUT_DIR/cpp"
    local f="$OUTPUT_DIR/cpp/neural_network.cpp"
    cat > "$f" <<'EOF'
// neural_network.cpp — idiomatic C++17: flat row-major storage, <numeric>
// algorithms, anonymous namespace, [[nodiscard]].
// Build: g++ -O2 -std=c++17 neural_network.cpp -o nn && ./nn
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

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdio>
#include <numeric>
#include <random>
#include <vector>

namespace {

constexpr double kLearningRate = __LR__;
constexpr int kEpochs = __EPOCHS__;

double sigmoid(double x) noexcept { return 1.0 / (1.0 + std::exp(-x)); }

class Mlp {
public:
    Mlp(std::size_t n_in, std::size_t n_hidden, std::size_t n_out, double lr,
        std::uint32_t seed = 42)
        : n_in_{n_in}, n_hid_{n_hidden}, n_out_{n_out}, lr_{lr},
          w1_(n_in * n_hidden), b1_(n_hidden, 0.0),
          w2_(n_hidden * n_out), b2_(n_out, 0.0), hidden_(n_hidden) {
        // He-style init: normal(0, sqrt(2/fan_in)) keeps activations healthy.
        auto normal = [engine = std::mt19937{seed}](double sigma) mutable {
            return std::normal_distribution<double>{0.0, sigma}(engine);
        };
        for (double& w : w1_) w = normal(std::sqrt(2.0 / static_cast<double>(n_in)));
        for (double& w : w2_) w = normal(std::sqrt(2.0 / static_cast<double>(n_hidden)));
    }

    /// Forward pass; hidden activations are cached internally for train_step().
    [[nodiscard]] std::vector<double> forward(const std::vector<double>& x) {
        for (std::size_t j = 0; j < n_hid_; ++j)
            hidden_[j] = sigmoid(b1_[j] + dot(x, j, w1_, n_hid_));
        std::vector<double> out(n_out_);
        for (std::size_t k = 0; k < n_out_; ++k)
            out[k] = sigmoid(b2_[k] + dot(hidden_, k, w2_, n_out_));
        return out;
    }

    /// One SGD step on a single sample; returns its squared error.
    double train_step(const std::vector<double>& x, const std::vector<double>& y) {
        const std::vector<double> out = forward(x);

        // Output delta: error times sigmoid'(out) = out*(1-out).
        std::vector<double> d_out(n_out_);
        std::transform(out.cbegin(), out.cend(), y.cbegin(), d_out.begin(),
                       [](double o, double t) { return (o - t) * o * (1.0 - o); });

        // Hidden delta: backpropagated error (via W2 row) times sigmoid'(h).
        std::vector<double> d_hid(n_hid_);
        for (std::size_t j = 0; j < n_hid_; ++j) {
            const double back = std::inner_product(
                d_out.cbegin(), d_out.cend(),
                w2_.cbegin() + static_cast<std::ptrdiff_t>(j * n_out_), 0.0);
            const double a = hidden_[j];
            d_hid[j] = back * a * (1.0 - a);
        }

        // Gradient descent: each weight moves against its gradient.
        for (std::size_t j = 0; j < n_hid_; ++j)
            for (std::size_t k = 0; k < n_out_; ++k)
                w2_[j * n_out_ + k] -= lr_ * d_out[k] * hidden_[j];
        std::transform(d_out.cbegin(), d_out.cend(), b2_.begin(),
                       [lr = lr_](double d, double b) { return b - lr * d; });
        for (std::size_t i = 0; i < n_in_; ++i)
            for (std::size_t j = 0; j < n_hid_; ++j)
                w1_[i * n_hid_ + j] -= lr_ * d_hid[j] * x[i];
        std::transform(d_hid.cbegin(), d_hid.cend(), b1_.begin(),
                       [lr = lr_](double d, double b) { return b - lr * d; });

        return std::transform_reduce(out.cbegin(), out.cend(), y.cbegin(), 0.0,
                                     std::plus<>{},
                                     [](double o, double t) { return (o - t) * (o - t); });
    }

private:
    /// v . w[:, col] for a row-major matrix w with the given stride.
    [[nodiscard]] double dot(const std::vector<double>& v, std::size_t col,
                             const std::vector<double>& w, std::size_t stride) const {
        double sum = 0.0;
        std::size_t idx = col;
        for (const double vi : v) {
            sum += vi * w[idx];
            idx += stride;
        }
        return sum;
    }

    std::size_t n_in_, n_hid_, n_out_;
    double lr_;
    std::vector<double> w1_, b1_, w2_, b2_, hidden_;
};

}  // namespace

int main() {
    constexpr std::size_t kIn = __INPUT__, kHid = __HIDDEN__, kOut = __OUTPUT__;

    Mlp net(kIn, kHid, kOut, kLearningRate);

    std::mt19937 rng{7};  // toy dataset — replace with your own
    auto uniform = [&rng] { return std::uniform_real_distribution<double>{0.0, 1.0}(rng); };
    std::vector<std::vector<double>> x(64, std::vector<double>(kIn));
    std::vector<std::vector<double>> y(64, std::vector<double>(kOut));
    for (auto& row : x) std::generate(row.begin(), row.end(), uniform);
    for (auto& row : y) std::generate(row.begin(), row.end(), uniform);

    const int show_every = std::max(kEpochs / 10, 1);
    for (int epoch = 1; epoch <= kEpochs; ++epoch) {
        double loss = 0.0;
        for (std::size_t s = 0; s < x.size(); ++s)
            loss += net.train_step(x[s], y[s]);
        if (epoch % show_every == 0)
            std::printf("epoch %5d  mse = %.6f\n", epoch, loss / static_cast<double>(x.size()));
    }
}
EOF
    fill_placeholders "$f"
    cat > "$OUTPUT_DIR/cpp/Makefile" <<'EOF'
CXX      ?= g++
CXXFLAGS ?= -O2 -std=c++17 -Wall

nn: neural_network.cpp
    $(CXX) $(CXXFLAGS) neural_network.cpp -o nn

run: nn
    ./nn

clean:
    rm -f nn

.PHONY: run clean
EOF
    add_file "$OUTPUT_DIR/cpp/neural_network.cpp"
    add_file "$OUTPUT_DIR/cpp/Makefile"
}

gen_c() {
    mkdir -p "$OUTPUT_DIR/c"
    local f="$OUTPUT_DIR/c/neural_network.c"
    cat > "$f" <<'EOF'
/* neural_network.c — idiomatic C99: xmalloc, struct-owned scratch buffers,
 * const-correct API, create/destroy lifecycle.
 * Build: cc -O2 -std=c99 neural_network.c -o nn -lm && ./nn
 *
 * HOW IT WORKS
 * ------------
 * Network: n_in -> n_hidden (sigmoid) -> n_out (sigmoid), trained by SGD
 * on mean squared error.
 *
 * FORWARD   hidden[j] = sigmoid(b1[j] + sum_i x[i] * w1[i*n_hid + j])
 *           out[k]    = sigmoid(b2[k] + sum_j hidden[j] * w2[j*n_out + k])
 *           sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)
 *
 * BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
 *           d_out[k]    = (out[k] - y[k]) * out[k] * (1 - out[k])
 *           d_hidden[j] = (sum_k d_out[k] * w2[j*n_out+k]) * h[j] * (1 - h[j])
 *
 * UPDATE    every gradient = delta * activation feeding that edge:
 *           w2[j*n_out+k] -= lr * d_out[k] * hidden[j]
 *           w1[i*n_hid+j] -= lr * d_hidden[j] * x[i]
 *           b1/b2 shift by lr * their delta.
 *
 * Replace the "toy dataset" block in main() with real data to train on it.
 */

#include <math.h>
#include <stdio.h>
#include <stdlib.h>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

/* ---------- checked allocation (xmalloc idiom) ---------- */

static void *xmalloc(size_t n)
{
    void *p = malloc(n);
    if (!p) {
        fputs("fatal: out of memory\n", stderr);
        exit(EXIT_FAILURE);
    }
    return p;
}

/* ---------- deterministic SplitMix64 PRNG ---------- */

typedef struct { unsigned long long state; } Rng;

static double rng_uniform(Rng *r)
{
    r->state = r->state * 6364136223846793005ULL + 1442695040888963407ULL;
    return (double)(r->state >> 11) / 9007199254740992.0; /* 2^53 */
}

static double rng_normal(Rng *r)
{
    double u = rng_uniform(r);
    if (u < 1e-12) u = 1e-12;
    return sqrt(-2.0 * log(u)) * cos(2.0 * M_PI * rng_uniform(r));
}

static double sigmoid(double x) { return 1.0 / (1.0 + exp(-x)); }

/* ---------- network ---------- */

typedef struct {
    double lr;
    size_t n_in, n_hid, n_out;
    double *w1, *w2;                  /* row-major: w1[i*n_hid + j], w2[j*n_out + k] */
    double *b1, *b2;
    double *hidden, *out, *d_out, *d_hid;  /* scratch, owned by the struct */
} Mlp;

static Mlp mlp_create(size_t n_in, size_t n_hid, size_t n_out, double lr,
                      unsigned long long seed)
{
    Rng r = { seed };
    Mlp m;
    m.lr = lr;
    m.n_in = n_in; m.n_hid = n_hid; m.n_out = n_out;
    m.w1 = xmalloc(n_in * n_hid * sizeof *m.w1);
    m.w2 = xmalloc(n_hid * n_out * sizeof *m.w2);
    m.b1 = xmalloc(n_hid * sizeof *m.b1);
    m.b2 = xmalloc(n_out * sizeof *m.b2);
    m.hidden = xmalloc(n_hid * sizeof *m.hidden);
    m.out = xmalloc(n_out * sizeof *m.out);
    m.d_out = xmalloc(n_out * sizeof *m.d_out);
    m.d_hid = xmalloc(n_hid * sizeof *m.d_hid);
    for (size_t j = 0; j < n_hid; j++) m.b1[j] = 0.0;
    for (size_t k = 0; k < n_out; k++) m.b2[k] = 0.0;
    /* He-style init: scale by sqrt(2/fan_in). */
    const double s1 = sqrt(2.0 / (double)n_in), s2 = sqrt(2.0 / (double)n_hid);
    for (size_t i = 0; i < n_in * n_hid; i++) m.w1[i] = rng_normal(&r) * s1;
    for (size_t i = 0; i < n_hid * n_out; i++) m.w2[i] = rng_normal(&r) * s2;
    return m;
}

static void mlp_destroy(Mlp *m)
{
    free(m->w1); free(m->w2); free(m->b1); free(m->b2);
    free(m->hidden); free(m->out); free(m->d_out); free(m->d_hid);
}

/* Forward pass; the result also lives in m->out for train_step(). */
static const double *mlp_forward(Mlp *m, const double *x)
{
    for (size_t j = 0; j < m->n_hid; j++) {
        double s = m->b1[j];
        for (size_t i = 0; i < m->n_in; i++)
            s += x[i] * m->w1[i * m->n_hid + j];
        m->hidden[j] = sigmoid(s);
    }
    for (size_t k = 0; k < m->n_out; k++) {
        double s = m->b2[k];
        for (size_t j = 0; j < m->n_hid; j++)
            s += m->hidden[j] * m->w2[j * m->n_out + k];
        m->out[k] = sigmoid(s);
    }
    return m->out;
}

/* One SGD step on one sample; returns the sample's squared error. */
static double mlp_train_step(Mlp *m, const double *x, const double *y)
{
    const double *out = mlp_forward(m, x);

    double sq_err = 0.0;
    for (size_t k = 0; k < m->n_out; k++) {
        const double d = out[k] - y[k];
        m->d_out[k] = d * out[k] * (1.0 - out[k]);   /* error * sigmoid'(out) */
        sq_err += d * d;
    }
    for (size_t j = 0; j < m->n_hid; j++) {
        double back = 0.0;
        for (size_t k = 0; k < m->n_out; k++)
            back += m->d_out[k] * m->w2[j * m->n_out + k];
        const double a = m->hidden[j];
        m->d_hid[j] = back * a * (1.0 - a);          /* backprop * sigmoid'(h) */
    }
    for (size_t j = 0; j < m->n_hid; j++)
        for (size_t k = 0; k < m->n_out; k++)
            m->w2[j * m->n_out + k] -= m->lr * m->d_out[k] * m->hidden[j];
    for (size_t k = 0; k < m->n_out; k++) m->b2[k] -= m->lr * m->d_out[k];
    for (size_t i = 0; i < m->n_in; i++)
        for (size_t j = 0; j < m->n_hid; j++)
            m->w1[i * m->n_hid + j] -= m->lr * m->d_hid[j] * x[i];
    for (size_t j = 0; j < m->n_hid; j++) m->b1[j] -= m->lr * m->d_hid[j];
    return sq_err;
}

int main(void)
{
    enum { N_SAMPLES = 64 };
    const size_t n_in = __INPUT__, n_hid = __HIDDEN__, n_out = __OUTPUT__;
    const double lr = __LR__;
    const int epochs = __EPOCHS__;

    Mlp net = mlp_create(n_in, n_hid, n_out, lr, 42ULL);

    /* Toy dataset — replace with your own. */
    Rng data = { 7ULL };
    double **x = xmalloc(N_SAMPLES * sizeof *x);
    double **y = xmalloc(N_SAMPLES * sizeof *y);
    for (int s = 0; s < N_SAMPLES; s++) {
        x[s] = xmalloc(n_in * sizeof *x[s]);
        y[s] = xmalloc(n_out * sizeof *y[s]);
        for (size_t i = 0; i < n_in; i++) x[s][i] = rng_uniform(&data);
        for (size_t k = 0; k < n_out; k++) y[s][k] = rng_uniform(&data);
    }

    const int show_every = epochs / 10 > 0 ? epochs / 10 : 1;
    for (int ep = 1; ep <= epochs; ep++) {
        double loss = 0.0;
        for (int s = 0; s < N_SAMPLES; s++)
            loss += mlp_train_step(&net, x[s], y[s]);
        if (ep % show_every == 0)
            printf("epoch %5d  mse = %.6f\n", ep, loss / N_SAMPLES);
    }

    for (int s = 0; s < N_SAMPLES; s++) { free(x[s]); free(y[s]); }
    free(x); free(y);
    mlp_destroy(&net);
    return EXIT_SUCCESS;
}
EOF
    fill_placeholders "$f"
    cat > "$OUTPUT_DIR/c/Makefile" <<'EOF'
CC      ?= cc
CFLAGS  ?= -O2 -std=c99 -Wall -Wextra
LDLIBS  ?= -lm

nn: neural_network.c
    $(CC) $(CFLAGS) neural_network.c -o nn $(LDLIBS)

run: nn
    ./nn

clean:
    rm -f nn

.PHONY: run clean
EOF
    add_file "$OUTPUT_DIR/c/neural_network.c"
    add_file "$OUTPUT_DIR/c/Makefile"
}

gen_java() {
    mkdir -p "$OUTPUT_DIR/java"
    local f="$OUTPUT_DIR/java/NeuralNetwork.java"
    cat > "$f" <<'EOF'
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
        var hp = new HyperParams(__INPUT__, __HIDDEN__, __OUTPUT__, __LR__, __EPOCHS__);
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
EOF
    fill_placeholders "$f"
    add_file "$OUTPUT_DIR/java/NeuralNetwork.java"
}

gen_javascript() {
    mkdir -p "$OUTPUT_DIR/javascript"
    local f="$OUTPUT_DIR/javascript/neural_network.js"
    cat > "$f" <<'EOF'
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
EOF
    fill_placeholders "$f"

    local g="$OUTPUT_DIR/javascript/demo.js"
    cat > "$g" <<'EOF'
// demo.js — entry point. Run: node demo.js
import { NeuralNetwork } from "./neural_network.js";

const hyper = { nIn: __INPUT__, nHidden: __HIDDEN__, nOut: __OUTPUT__, lr: __LR__ };
const epochs = __EPOCHS__;
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
EOF
    fill_placeholders "$g"

    cat > "$OUTPUT_DIR/javascript/package.json" <<'EOF'
{
  "name": "neural-network-js",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": { "start": "node demo.js" }
}
EOF
    add_file "$OUTPUT_DIR/javascript/neural_network.js"
    add_file "$OUTPUT_DIR/javascript/demo.js"
    add_file "$OUTPUT_DIR/javascript/package.json"
}

gen_typescript() {
    mkdir -p "$OUTPUT_DIR/typescript"
    local f="$OUTPUT_DIR/typescript/neural_network.ts"
    cat > "$f" <<'EOF'
// neural_network.ts — idiomatic TypeScript: readonly interfaces, typed
// #private fields, NodeNext ESM, strict mode. Library module; see demo.ts.
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

export interface HyperParameters {
  readonly nIn: number;
  readonly nHidden: number;
  readonly nOut: number;
  readonly lr: number;
}

export const sigmoid = (x: number): number => 1 / (1 + Math.exp(-x));

/** Box-Muller transform on top of an injectable uniform source. */
export function gaussian(random: () => number = Math.random): number {
  let u = random();
  while (u === 0) u = random();
  const v = random();
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
}

/** He-initialised weight matrix, flat and row-major. */
export function heMatrix(rows: number, cols: number, random: () => number = Math.random): Float64Array {
  const scale = Math.sqrt(2 / rows);
  const w = new Float64Array(rows * cols);
  for (let i = 0; i < w.length; i++) w[i] = gaussian(random) * scale;
  return w;
}

export class NeuralNetwork {
  #lr: number;
  #nIn: number;
  #nHidden: number;
  #nOut: number;
  #w1: Float64Array;
  #b1: Float64Array;
  #w2: Float64Array;
  #b2: Float64Array;
  #hidden: Float64Array;

  constructor({ nIn, nHidden, nOut, lr }: HyperParameters, random: () => number = Math.random) {
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

  forward(x: ArrayLike<number>): Float64Array {
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

  trainStep(x: ArrayLike<number>, y: ArrayLike<number>): number {
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
EOF
    fill_placeholders "$f"

    local g="$OUTPUT_DIR/typescript/demo.ts"
    cat > "$g" <<'EOF'
// demo.ts — entry point. Run: npx tsx demo.ts   (or: npm run build && npm run start:compiled)
import { NeuralNetwork, type HyperParameters } from "./neural_network.js";

const hyper: HyperParameters = {
  nIn: __INPUT__,
  nHidden: __HIDDEN__,
  nOut: __OUTPUT__,
  lr: __LR__,
};
const epochs = __EPOCHS__;

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
    console.log(
      `epoch ${String(epoch).padStart(5)}  mse = ${(loss / dataset.length).toFixed(6)}`,
    );
  }
}
EOF
    fill_placeholders "$g"

    cat > "$OUTPUT_DIR/typescript/package.json" <<'EOF'
{
  "name": "neural-network-ts",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "start": "tsx demo.ts",
    "build": "tsc",
    "start:compiled": "node dist/demo.js"
  },
  "devDependencies": {
    "@types/node": "^22.0.0",
    "tsx": "^4.19.0",
    "typescript": "^5.6.0"
  }
}
EOF

    cat > "$OUTPUT_DIR/typescript/tsconfig.json" <<'EOF'
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "outDir": "dist",
    "strict": true,
    "declaration": true,
    "verbatimModuleSyntax": true,
    "forceConsistentCasingInFileNames": true,
    "skipLibCheck": true
  },
  "include": ["neural_network.ts", "demo.ts"]
}
EOF
    add_file "$OUTPUT_DIR/typescript/neural_network.ts"
    add_file "$OUTPUT_DIR/typescript/demo.ts"
    add_file "$OUTPUT_DIR/typescript/package.json"
    add_file "$OUTPUT_DIR/typescript/tsconfig.json"
}

gen_go() {
    mkdir -p "$OUTPUT_DIR/go"
    local f="$OUTPUT_DIR/go/main.go"
    cat > "$f" <<'EOF'
// main.go — idiomatic Go: math/rand/v2 with PCG (no global seeding), doc
// comments, local value types, builtin max.
// Run: go run main.go   (Go 1.22+)
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
package main

import (
    "fmt"
    "math"
    "math/rand/v2"
)

// MLP is a one-hidden-layer network with sigmoid activations.
type MLP struct {
    lr              float64
    nIn, nHid, nOut int
    w1, w2          [][]float64
    b1, b2, hidden  []float64
}

// NewMLP returns a He-initialised network driven by rng.
func NewMLP(nIn, nHid, nOut int, lr float64, rng *rand.Rand) *MLP {
    nn := &MLP{
        lr: lr, nIn: nIn, nHid: nHid, nOut: nOut,
        w1: heMatrix(nIn, nHid, rng),
        w2: heMatrix(nHid, nOut, rng),
        b1: make([]float64, nHid),
        b2: make([]float64, nOut),
    }
    nn.hidden = make([]float64, nHid)
    return nn
}

// heMatrix fills a rows x cols matrix with N(0, 2/rows) values.
func heMatrix(rows, cols int, rng *rand.Rand) [][]float64 {
    scale := math.Sqrt(2 / float64(rows))
    m := make([][]float64, rows)
    for i := range m {
        m[i] = make([]float64, cols)
        for j := range m[i] {
            m[i][j] = rng.NormFloat64() * scale
        }
    }
    return m
}

func sigmoid(x float64) float64 { return 1 / (1 + math.Exp(-x)) }

// Forward computes the output for one sample and caches hidden activations.
func (nn *MLP) Forward(x []float64) []float64 {
    for j := range nn.hidden {
        s := nn.b1[j]
        for i, xi := range x {
            s += xi * nn.w1[i][j]
        }
        nn.hidden[j] = sigmoid(s)
    }
    out := make([]float64, nn.nOut)
    for k := range out {
        s := nn.b2[k]
        for j, h := range nn.hidden {
            s += h * nn.w2[j][k]
        }
        out[k] = sigmoid(s)
    }
    return out
}

// TrainStep performs one SGD update for a sample and returns its squared error.
func (nn *MLP) TrainStep(x, y []float64) float64 {
    out := nn.Forward(x)

    // Output delta: error times sigmoid'(out).
    dOut := make([]float64, nn.nOut)
    sqErr := 0.0
    for k, o := range out {
        dOut[k] = (o - y[k]) * o * (1 - o)
        sqErr += (o - y[k]) * (o - y[k])
    }

    // Hidden delta: backpropagated error times sigmoid'(hidden).
    dHid := make([]float64, nn.nHid)
    for j := range dHid {
        back := 0.0
        for k, d := range dOut {
            back += d * nn.w2[j][k]
        }
        dHid[j] = back * nn.hidden[j] * (1 - nn.hidden[j])
    }

    // Gradient descent: weight -= lr * delta * activation on that edge.
    for j, h := range nn.hidden {
        for k, d := range dOut {
            nn.w2[j][k] -= nn.lr * d * h
        }
    }
    for k, d := range dOut {
        nn.b2[k] -= nn.lr * d
    }
    for i, xi := range x {
        for j, d := range dHid {
            nn.w1[i][j] -= nn.lr * d * xi
        }
    }
    for j, d := range dHid {
        nn.b1[j] -= nn.lr * d
    }
    return sqErr
}

func main() {
    const (
        nIn, nHid, nOut = __INPUT__, __HIDDEN__, __OUTPUT__
        lr              = __LR__
        epochs          = __EPOCHS__
    )

    // Deterministic PCG streams — no rand.Seed, reproducible across platforms.
    nn := NewMLP(nIn, nHid, nOut, lr, rand.New(rand.NewPCG(42, 0)))

    // Toy dataset — replace with your own.
    type sample struct{ x, y []float64 }
    data := rand.New(rand.NewPCG(7, 0))
    dataset := make([]sample, 64)
    for i := range dataset {
        dataset[i] = sample{x: make([]float64, nIn), y: make([]float64, nOut)}
        for j := range dataset[i].x {
            dataset[i].x[j] = data.Float64()
        }
        for k := range dataset[i].y {
            dataset[i].y[k] = data.Float64()
        }
    }

    showEvery := max(epochs/10, 1)
    for epoch := 1; epoch <= epochs; epoch++ {
        loss := 0.0
        for _, s := range dataset {
            loss += nn.TrainStep(s.x, s.y)
        }
        if epoch%showEvery == 0 {
            fmt.Printf("epoch %5d  mse = %.6f\n", epoch, loss/float64(len(dataset)))
        }
    }
}
EOF
    fill_placeholders "$f"
    cat > "$OUTPUT_DIR/go/go.mod" <<'EOF'
module neuralnetwork

go 1.22
EOF
    add_file "$OUTPUT_DIR/go/main.go"
    add_file "$OUTPUT_DIR/go/go.mod"
}

gen_rust() {
    mkdir -p "$OUTPUT_DIR/rust/src"
    local f="$OUTPUT_DIR/rust/src/main.rs"
    cat > "$f" <<'EOF'
//! Idiomatic Rust: iterator pipelines over flat row-major storage, doc
//! comments, inline format args, and unit tests. No external crates.
//! Run: cargo run --release
//!
//! HOW IT WORKS
//! ------------
//! Network: n_in -> n_hidden (sigmoid) -> n_out (sigmoid), trained by SGD
//! on mean squared error.
//!
//! FORWARD   hidden[j] = sigmoid(b1[j] + sum_i x[i] * w1[i*n_hidden + j])
//!           out[k]    = sigmoid(b2[k] + sum_j hidden[j] * w2[j*n_out + k])
//!           sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)
//!
//! BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
//!           d_out[k]    = (out[k] - y[k]) * out[k] * (1 - out[k])
//!           d_hidden[j] = (sum_k d_out[k] * w2[j*n_out+k]) * h[j] * (1 - h[j])
//!
//! UPDATE    every gradient = delta * activation feeding that edge:
//!           w2[j][k] -= lr * d_out[k] * hidden[j]    b2[k] -= lr * d_out[k]
//!           w1[i][j] -= lr * d_hidden[j] * x[i]      b1[j] -= lr * d_hidden[j]
//!
//! Replace the "toy dataset" block in main() with real data to train on it.

#![forbid(unsafe_code)]

use std::f64::consts::PI;

/// Deterministic SplitMix64 PRNG (keeps the crate dependency-free).
struct Rng {
    state: u64,
}

impl Rng {
    fn new(seed: u64) -> Self {
        Self { state: seed }
    }

    /// Next uniform in [0, 1).
    fn uniform(&mut self) -> f64 {
        self.state = self
            .state
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        (self.state >> 11) as f64 / (1u64 << 53) as f64
    }

    /// Standard-normal draw via Box-Muller.
    fn normal(&mut self) -> f64 {
        let u = self.uniform().max(1e-12);
        (-2.0 * u.ln()).sqrt() * (2.0 * PI * self.uniform()).cos()
    }
}

fn sigmoid(x: f64) -> f64 {
    1.0 / (1.0 + (-x).exp())
}

/// v . w[offset], w[offset + stride], w[offset + 2*stride], ...
/// i.e. a dot product with one column of a row-major matrix.
fn dot_column(v: &[f64], w: &[f64], stride: usize) -> f64 {
    v.iter()
        .zip(w.iter().step_by(stride))
        .map(|(x, w)| x * w)
        .sum()
}

/// One-hidden-layer MLP with sigmoid activations, trained by SGD.
#[derive(Debug, Clone)]
struct NeuralNetwork {
    lr: f64,
    n_in: usize,
    n_hidden: usize,
    n_out: usize,
    /// Row-major [n_in x n_hidden].
    w1: Vec<f64>,
    b1: Vec<f64>,
    /// Row-major [n_hidden x n_out].
    w2: Vec<f64>,
    b2: Vec<f64>,
    /// Hidden activations cached by the last [`forward`].
    hidden: Vec<f64>,
}

impl NeuralNetwork {
    fn new(n_in: usize, n_hidden: usize, n_out: usize, lr: f64, seed: u64) -> Self {
        let mut rng = Rng::new(seed);
        let he = |rows: usize, cols: usize| {
            let scale = (2.0 / rows as f64).sqrt();
            std::iter::repeat_with(|| rng.normal() * scale)
                .take(rows * cols)
                .collect::<Vec<f64>>()
        };
        Self {
            lr,
            n_in,
            n_hidden,
            n_out,
            w1: he(n_in, n_hidden),
            b1: vec![0.0; n_hidden],
            w2: he(n_hidden, n_out),
            b2: vec![0.0; n_out],
            hidden: vec![0.0; n_hidden],
        }
    }

    /// Forward pass for one sample; caches hidden activations for `train_step`.
    fn forward(&mut self, x: &[f64]) -> Vec<f64> {
        for (j, h) in self.hidden.iter_mut().enumerate() {
            *h = sigmoid(self.b1[j] + dot_column(x, &self.w1[j..], self.n_hidden));
        }
        (0..self.n_out)
            .map(|k| sigmoid(self.b2[k] + dot_column(&self.hidden, &self.w2[k..], self.n_out)))
            .collect()
    }

    /// One SGD step for a sample; returns the sample's squared error.
    fn train_step(&mut self, x: &[f64], y: &[f64]) -> f64 {
        let out = self.forward(x);

        let d_out: Vec<f64> = out
            .iter()
            .zip(y)
            .map(|(o, t)| (o - t) * o * (1.0 - o))       // error * sigmoid'(out)
            .collect();
        let sq_err: f64 = out.iter().zip(y).map(|(o, t)| (o - t) * (o - t)).sum();

        let d_hidden: Vec<f64> = (0..self.n_hidden)
            .map(|j| {
                let back = dot_column(&d_out, &self.w2[j..], self.n_out);
                back * self.hidden[j] * (1.0 - self.hidden[j])  // * sigmoid'(h)
            })
            .collect();

        // w2 -= lr * d_out (outer) hidden — rank-1 update per row.
        for (j, &h) in self.hidden.iter().enumerate() {
            let row = &mut self.w2[j * self.n_out..(j + 1) * self.n_out];
            for (k, w) in row.iter_mut().enumerate() {
                *w -= self.lr * d_out[k] * h;
            }
        }
        for (b, d) in self.b2.iter_mut().zip(&d_out) {
            *b -= self.lr * d;
        }
        for (i, &xi) in x.iter().enumerate() {
            for (j, &d) in d_hidden.iter().enumerate() {
                self.w1[i * self.n_hidden + j] -= self.lr * d * xi;
            }
        }
        for (b, d) in self.b1.iter_mut().zip(&d_hidden) {
            *b -= self.lr * d;
        }
        sq_err
    }
}

fn main() {
    let n_in: usize = __INPUT__;
    let n_hidden: usize = __HIDDEN__;
    let n_out: usize = __OUTPUT__;
    let lr: f64 = __LR__;
    let epochs: usize = __EPOCHS__;

    let mut net = NeuralNetwork::new(n_in, n_hidden, n_out, lr, 42);

    // Toy dataset — replace with your own.
    let mut data = Rng::new(7);
    let dataset: Vec<(Vec<f64>, Vec<f64>)> = std::iter::repeat_with(|| {
        (
            std::iter::repeat_with(|| data.uniform()).take(n_in).collect(),
            std::iter::repeat_with(|| data.uniform()).take(n_out).collect(),
        )
    })
    .take(64)
    .collect();

    let show_every = (epochs / 10).max(1);
    for epoch in 1..=epochs {
        let loss: f64 = dataset.iter().map(|(x, y)| net.train_step(x, y)).sum();
        if epoch % show_every == 0 {
            println!("epoch {epoch:5}  mse = {loss:.6}");
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sigmoid_at_zero_is_one_half() {
        assert!((sigmoid(0.0) - 0.5).abs() < 1e-12);
    }

    #[test]
    fn training_reduces_error_on_a_single_sample() {
        let mut net = NeuralNetwork::new(1, 4, 1, 0.9, 7);
        let (x, y) = ([0.8], [1.0]);
        let err = |net: &mut NeuralNetwork| (net.forward(&x)[0] - y[0]).powi(2);
        let before = err(&mut net);
        for _ in 0..50 {
            net.train_step(&x, &y);
        }
        assert!(err(&mut net) < before, "loss should decrease");
    }
}
EOF
    fill_placeholders "$f"
    cat > "$OUTPUT_DIR/rust/Cargo.toml" <<'EOF'
[package]
name = "neural_network"
version = "0.1.0"
edition = "2021"

[dependencies]
EOF
    add_file "$OUTPUT_DIR/rust/src/main.rs"
    add_file "$OUTPUT_DIR/rust/Cargo.toml"
}

gen_ruby() {
    mkdir -p "$OUTPUT_DIR/ruby"
    local f="$OUTPUT_DIR/ruby/neural_network.rb"
    cat > "$f" <<'EOF'
# frozen_string_literal: true

# neural_network.rb — idiomatic Ruby: stdlib `matrix` for all linear algebra,
# Struct value objects, endless method definitions, pattern matching.
# Run: ruby neural_network.rb   (Ruby 3.0+; `matrix` ships with Ruby)
#
# HOW IT WORKS
# ------------
# Network: n_in -> n_hidden (sigmoid) -> n_out (sigmoid), trained by SGD
# on mean squared error.
#
# FORWARD   hidden = sigmoid(W1.t * x + b1)        (Vector ops, whole-layer)
#           out    = sigmoid(W2 * hidden + b2)
#           sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)
#
# BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
#           d_out    = (out - y) * out * (1 - out)
#           d_hidden = (W2 * d_out) * hidden * (1 - hidden)
#
# UPDATE    every gradient = delta (outer) activation feeding that edge:
#           W2 -= lr * hidden.d_out     b2 -= lr * d_out
#           W1 -= lr * x.d_hidden       b1 -= lr * d_hidden
#           (column_vector * row_vector = outer product)
#
# Replace the "toy dataset" block below with real data to train on it.

require 'matrix'

HyperParameters = Struct.new(:n_in, :n_hidden, :n_out, :lr, keyword_init: true) do
  def validate
    raise ArgumentError, 'layer sizes must be positive' unless [n_in, n_hidden, n_out].all? { _1 >= 1 }
    raise ArgumentError, 'lr must be positive' unless lr.positive?

    self
  end
end

class NeuralNetwork
  attr_reader :hyper, :w1, :w2, :b1, :b2

  def initialize(hyper, rng: Random.new(42))
    @hyper = hyper.validate
    @w1 = he_matrix(hyper.n_in, hyper.n_hidden, rng)
    @b1 = Vector.zero(hyper.n_hidden)
    @w2 = he_matrix(hyper.n_hidden, hyper.n_out, rng)
    @b2 = Vector.zero(hyper.n_out)
  end

  # Forward pass for one input Vector; caches hidden activations.
  def forward(x)
    @hidden = (w1.t * x + b1).map { |z| sigmoid(z) }
    (w2 * @hidden + b2).map { |z| sigmoid(z) }
  end

  # One SGD step on one sample (Vectors); returns its squared error.
  def train_step(x, y)
    out = forward(x)
    y_vec = Vector.elements(y.to_a)

    # Deltas per the chain rule; sigmoid'(a) = a * (1 - a).
    d_out = out.map2(y_vec) { |o, t| (o - t) * o * (1 - o) }
    d_hidden = Vector.elements(
      (0...hyper.n_hidden).map do |j|
        a = @hidden[j]
        w2.row(j).inner_product(d_out) * a * (1 - a)
      end
    )

    # Outer-product weight updates; column * row = matrix of rank 1.
    @w2 -= Matrix.column_vector(@hidden) * Matrix.row_vector(d_out) * hyper.lr
    @b2 -= d_out * hyper.lr
    @w1 -= Matrix.column_vector(x) * Matrix.row_vector(d_hidden) * hyper.lr
    @b1 -= d_hidden * hyper.lr

    (out - y_vec).to_a.sum { |e| e * e }
  end

  private

  def sigmoid(z) = 1.0 / (1.0 + Math.exp(-z))

  def he_matrix(rows, cols, rng)
    scale = Math.sqrt(2.0 / rows)
    Matrix.build(rows, cols) { rng.gauss * scale }
  end
end

# ---- demo (replace with your own data) ------------------------------
EPOCHS = __EPOCHS__

hyper = HyperParameters.new(n_in: __INPUT__, n_hidden: __HIDDEN__,
                            n_out: __OUTPUT__, lr: __LR__)
nn = NeuralNetwork.new(hyper)

rng = Random.new(7)
dataset = Array.new(64) do
  { x: Vector.elements(Array.new(hyper.n_in) { rng.rand }),
    y: Vector.elements(Array.new(hyper.n_out) { rng.rand }) }
end

show_every = [EPOCHS / 10, 1].max
(1..EPOCHS).each do |epoch|
  loss = dataset.sum do |sample|
    sample => { x:, y: }          # pattern-match destructuring
    nn.train_step(x, y)
  end
  puts format('epoch %5d  mse = %.6f', epoch, loss / dataset.size) if (epoch % show_every).zero?
end
EOF
    fill_placeholders "$f"
    chmod +x "$f"
    add_file "$OUTPUT_DIR/ruby/neural_network.rb"
}

gen_kotlin() {
    mkdir -p "$OUTPUT_DIR/kotlin"
    local f="$OUTPUT_DIR/kotlin/NeuralNetwork.kt"
    cat > "$f" <<'EOF'
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
    val hyper = HyperParameters(nIn = __INPUT__, nHidden = __HIDDEN__, nOut = __OUTPUT__, lr = __LR__)
    val epochs = __EPOCHS__
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
EOF
    fill_placeholders "$f"
    add_file "$OUTPUT_DIR/kotlin/NeuralNetwork.kt"
}

gen_swift() {
    mkdir -p "$OUTPUT_DIR/swift"
    local f="$OUTPUT_DIR/swift/main.swift"
    cat > "$f" <<'EOF'
// main.swift — idiomatic Swift: value-type struct with mutating methods,
// RandomNumberGenerator protocol, `inout some`, labeled tuples, free Codable.
// Run:   swift main.swift        Build: swiftc -O main.swift -o nn && ./nn
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

/// Deterministic PRNG (SplitMix64); conforming to RandomNumberGenerator
/// unlocks `Double.random(in:using:)` everywhere.
struct SplitMix64: RandomNumberGenerator {
    private var state: UInt64
    init(seed: UInt64) { state = seed }
    mutating func next() -> UInt64 {
        state = state &* 6364136223846793005 &+ 1442695040888963407
        return state
    }
}

/// Box-Muller standard-normal draw.
func gaussian(using rng: inout some RandomNumberGenerator) -> Double {
    var u = Double.random(in: 0..<1, using: &rng)
    if u < 1e-12 { u = 1e-12 }
    let v = Double.random(in: 0..<1, using: &rng)
    return (-2 * log(u)).squareRoot() * cos(2 * .pi * v)
}

func sigmoid(_ x: Double) -> Double { 1 / (1 + exp(-x)) }

/// One-hidden-layer MLP. A struct: value semantics make copying explicit and
/// cheap, and `Codable` comes for free.
struct NeuralNetwork {
    private let lr: Double
    private let nIn: Int, nHidden: Int, nOut: Int
    private var w1: [[Double]], b1: [Double]
    private var w2: [[Double]], b2: [Double]
    private var hidden: [Double] = []

    init(nIn: Int, nHidden: Int, nOut: Int, lr: Double, seed: UInt64 = 42) {
        precondition(min(nIn, nHidden, nOut) > 0 && lr > 0, "invalid hyperparameters")
        self.lr = lr
        (self.nIn, self.nHidden, self.nOut) = (nIn, nHidden, nOut)
        var rng = SplitMix64(seed: seed)
        w1 = Self.heMatrix(nIn, nHidden, &rng)      // He-style init
        b1 = .init(repeating: 0, count: nHidden)
        w2 = Self.heMatrix(nHidden, nOut, &rng)
        b2 = .init(repeating: 0, count: nOut)
    }

    private static func heMatrix(_ rows: Int, _ cols: Int, _ rng: inout SplitMix64) -> [[Double]] {
        let scale = (2.0 / Double(rows)).squareRoot()
        return (0..<rows).map { _ in (0..<cols).map { _ in gaussian(using: &rng) * scale } }
    }

    /// Forward pass for one sample; caches hidden activations for `trainStep`.
    mutating func forward(_ x: [Double]) -> [Double] {
        hidden = (0..<nHidden).map { j -> Double in
            let z = b1[j] + zip(x, w1).reduce(0.0) { $0 + $1.0 * $1.1[j] }
            return sigmoid(z)
        }
        return (0..<nOut).map { k -> Double in
            let z = b2[k] + zip(hidden, w2).reduce(0.0) { $0 + $1.0 * $1.1[k] }
            return sigmoid(z)
        }
    }

    /// One SGD step; returns the sample's squared error.
    mutating func trainStep(_ x: [Double], _ y: [Double]) -> Double {
        let out = forward(x)

        // Output delta: error times sigmoid'(out).
        let dOut = zip(out, y).map { o, t in (o - t) * o * (1 - o) }
        // Hidden delta: backpropagated error times sigmoid'(hidden).
        let dHidden = (0..<nHidden).map { j -> Double in
            let back = zip(dOut, w2[j]).reduce(0.0) { $0 + $1.0 * $1.1 }
            return back * hidden[j] * (1 - hidden[j])
        }

        // Gradient descent: weight -= lr * delta * activation on that edge.
        for j in 0..<nHidden {
            for k in 0..<nOut { w2[j][k] -= lr * dOut[k] * hidden[j] }
        }
        for k in 0..<nOut { b2[k] -= lr * dOut[k] }
        for (i, xi) in x.enumerated() {
            for (j, d) in dHidden.enumerated() { w1[i][j] -= lr * d * xi }
        }
        for (j, d) in dHidden.enumerated() { b1[j] -= lr * d }

        return zip(out, y).reduce(0.0) { $0 + ($1.0 - $1.1) * ($1.0 - $1.1) }
    }
}

// Value types get Codable synthesis with a one-liner — persistence for free.
extension NeuralNetwork: Codable {}

// ---- demo (replace with your own data) ------------------------------
let (nIn, nHidden, nOut) = (__INPUT__, __HIDDEN__, __OUTPUT__)
let (lr, epochs) = (__LR__, __EPOCHS__)

var net = NeuralNetwork(nIn: nIn, nHidden: nHidden, nOut: nOut, lr: lr)

var dataRng = SplitMix64(seed: 7)
let dataset = (0..<64).map { _ in
    (x: (0..<nIn).map { _ in Double.random(in: 0..<1, using: &dataRng) },
     y: (0..<nOut).map { _ in Double.random(in: 0..<1, using: &dataRng) })
}

let showEvery = max(epochs / 10, 1)
for epoch in 1...epochs {
    let loss = dataset.reduce(0.0) { $0 + net.trainStep($1.x, $1.y) }
    if epoch % showEvery == 0 {
        print(String(format: "epoch %5d  mse = %.6f", epoch, loss / Double(dataset.count)))
    }
}
EOF
    fill_placeholders "$f"
    add_file "$OUTPUT_DIR/swift/main.swift"
}

gen_csharp() {
    mkdir -p "$OUTPUT_DIR/csharp"
    local f="$OUTPUT_DIR/csharp/Program.cs"
    cat > "$f" <<'EOF'
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

const int nIn = __INPUT__, nHidden = __HIDDEN__, nOut = __OUTPUT__;
const double lr = __LR__;
const int epochs = __EPOCHS__;

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
EOF
    fill_placeholders "$f"
    cat > "$OUTPUT_DIR/csharp/NeuralNetwork.csproj" <<'EOF'
<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net8.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>enable</Nullable>
    <RootNamespace>NeuralNetworkDemo</RootNamespace>
  </PropertyGroup>
</Project>
EOF
    add_file "$OUTPUT_DIR/csharp/Program.cs"
    add_file "$OUTPUT_DIR/csharp/NeuralNetwork.csproj"
}

gen_dart() {
    mkdir -p "$OUTPUT_DIR/dart"
    local f="$OUTPUT_DIR/dart/main.dart"
    cat > "$f" <<'EOF'
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
  const nIn = __INPUT__;
  const nHidden = __HIDDEN__;
  const nOut = __OUTPUT__;
  const lr = __LR__;
  const epochs = __EPOCHS__;

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
EOF
    fill_placeholders "$f"
    add_file "$OUTPUT_DIR/dart/main.dart"
}

gen_php() {
    mkdir -p "$OUTPUT_DIR/php"
    local f="$OUTPUT_DIR/php/neural_network.php"
    cat > "$f" <<'EOF'
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
const N_IN = __INPUT__;
const N_HIDDEN = __HIDDEN__;
const N_OUT = __OUTPUT__;
const LEARNING_RATE = __LR__;
const EPOCHS = __EPOCHS__;

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
EOF
    fill_placeholders "$f"
    add_file "$OUTPUT_DIR/php/neural_network.php"
}

gen_perl() {
    mkdir -p "$OUTPUT_DIR/perl"
    local f="$OUTPUT_DIR/perl/neural_network.pl"
    cat > "$f" <<'EOF'
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
    n_in     => __INPUT__,
    n_hidden => __HIDDEN__,
    n_out    => __OUTPUT__,
    lr       => __LR__,
);

my ($N_IN, $N_OUT) = (__INPUT__, __OUTPUT__);
my ($epochs, $show_every) = (__EPOCHS__, int(__EPOCHS__ / 10) || 1);

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
EOF
    fill_placeholders "$f"
    chmod +x "$f"
    add_file "$OUTPUT_DIR/perl/neural_network.pl"
}
gen_lua() {
    mkdir -p "$OUTPUT_DIR/lua"
    local f="$OUTPUT_DIR/lua/neural_network.lua"
    cat > "$f" <<'EOF'
-- neural_network.lua — idiomatic Lua: metatable OOP, colon syntax, 1-based
-- tables, cached math locals. Run: lua neural_network.lua  (Lua 5.1+/LuaJIT)
--
-- HOW IT WORKS
-- ------------
-- Network: n_in -> n_hidden (sigmoid) -> n_out (sigmoid), trained by SGD on MSE.
--
-- FORWARD   hidden[j] = sigmoid(b1[j] + sum_i x[i] * w1[i][j])
--           out[k]    = sigmoid(b2[k] + sum_j hidden[j] * w2[j][k])
--           sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)
--
-- BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
--           d_out[k]    = (out[k] - y[k]) * out[k] * (1 - out[k])
--           d_hidden[j] = (sum_k d_out[k] * w2[j][k]) * hidden[j] * (1 - hidden[j])
--
-- UPDATE    every gradient = delta * activation feeding that edge:
--           w2[j][k] -= lr * d_out[k] * hidden[j]    b2[k] -= lr * d_out[k]
--           w1[i][j] -= lr * d_hidden[j] * x[i]      b1[j] -= lr * d_hidden[j]
--
-- Lua tables are 1-based, so loops run 1..n.
-- Replace the "toy dataset" block at the bottom with real data to train on it.

local exp, sqrt, cos, log, pi = math.exp, math.sqrt, math.cos, math.log, math.pi
local floor, max = math.floor, math.max

local function sigmoid(x)
  return 1.0 / (1.0 + exp(-x))
end

-- Box-Muller standard normal (Lua has no built-in gaussian).
local function gauss()
  local u = math.random()
  while u == 0.0 do u = math.random() end
  return sqrt(-2.0 * log(u)) * cos(2.0 * pi * math.random())
end

-- He-style init: N(0, sqrt(2/rows)).
local function rand_matrix(rows, cols)
  local scale = sqrt(2.0 / rows)
  local m = {}
  for i = 1, rows do
    m[i] = {}
    for j = 1, cols do
      m[i][j] = gauss() * scale
    end
  end
  return m
end

local function zeros(n)
  local t = {}
  for i = 1, n do t[i] = 0.0 end
  return t
end

local NeuralNetwork = {}
NeuralNetwork.__index = NeuralNetwork

function NeuralNetwork.new(n_in, n_hid, n_out, lr)
  local self = setmetatable({}, NeuralNetwork)
  self.lr, self.n_in, self.n_hid, self.n_out = lr, n_in, n_hid, n_out
  self.w1 = rand_matrix(n_in, n_hid)
  self.b1 = zeros(n_hid)
  self.w2 = rand_matrix(n_hid, n_out)
  self.b2 = zeros(n_out)
  self.a1 = zeros(n_hid)
  return self
end

-- Forward pass; caches hidden activations in self.a1 for train_step.
function NeuralNetwork:forward(x)
  for j = 1, self.n_hid do
    local s = self.b1[j]
    for i = 1, self.n_in do
      s = s + x[i] * self.w1[i][j]
    end
    self.a1[j] = sigmoid(s)
  end
  local out = {}
  for k = 1, self.n_out do
    local s = self.b2[k]
    for j = 1, self.n_hid do
      s = s + self.a1[j] * self.w2[j][k]
    end
    out[k] = sigmoid(s)
  end
  return out
end

-- One SGD step; returns the sample's squared error.
function NeuralNetwork:train_step(x, y)
  local out = self:forward(x)

  -- Output delta: error times sigmoid'(out).
  local d2 = {}
  for k = 1, self.n_out do
    d2[k] = (out[k] - y[k]) * out[k] * (1.0 - out[k])
  end

  -- Hidden delta: backpropagated error times sigmoid'(hidden).
  local d1 = {}
  for j = 1, self.n_hid do
    local s = 0.0
    for k = 1, self.n_out do
      s = s + d2[k] * self.w2[j][k]
    end
    d1[j] = s * self.a1[j] * (1.0 - self.a1[j])
  end

  -- Gradient descent: weight -= lr * delta * activation on that edge.
  for j = 1, self.n_hid do
    for k = 1, self.n_out do
      self.w2[j][k] = self.w2[j][k] - self.lr * d2[k] * self.a1[j]
    end
  end
  for k = 1, self.n_out do
    self.b2[k] = self.b2[k] - self.lr * d2[k]
  end
  for i = 1, self.n_in do
    for j = 1, self.n_hid do
      self.w1[i][j] = self.w1[i][j] - self.lr * d1[j] * x[i]
    end
  end
  for j = 1, self.n_hid do
    self.b1[j] = self.b1[j] - self.lr * d1[j]
  end

  local sq = 0.0
  for k = 1, self.n_out do
    local d = out[k] - y[k]
    sq = sq + d * d
  end
  return sq
end

-- ---- demo (replace with your own data) ------------------------------
math.randomseed(42)
local N_IN, N_HID, N_OUT = __INPUT__, __HIDDEN__, __OUTPUT__
local LR, EPOCHS = __LR__, __EPOCHS__

local nn = NeuralNetwork.new(N_IN, N_HID, N_OUT, LR)

math.randomseed(7)
local x, y = {}, {}
for s = 1, 64 do
  x[s], y[s] = {}, {}
  for i = 1, N_IN do x[s][i] = math.random() end
  for k = 1, N_OUT do y[s][k] = math.random() end
end

local show_every = max(floor(EPOCHS / 10), 1)
for ep = 1, EPOCHS do
  local loss = 0.0
  for s = 1, 64 do
    loss = loss + nn:train_step(x[s], y[s])
  end
  if ep % show_every == 0 then
    print(string.format("epoch %5d  mse = %.6f", ep, loss / 64))
  end
end
EOF
    fill_placeholders "$f"
    add_file "$OUTPUT_DIR/lua/neural_network.lua"
}

gen_haskell() {
    mkdir -p "$OUTPUT_DIR/haskell"
    local f="$OUTPUT_DIR/haskell/Main.hs"
    cat > "$f" <<'EOF'
-- Main.hs — idiomatic Haskell: a pure interface over controlled mutation.
-- Weights are unboxed arrays updated inside `ST` for one epoch, then frozen
-- back into an immutable record — the "mutable core, pure shell" pattern.
-- `array` ships with GHC, so this still installs nothing.
-- Run:   runghc Main.hs        Build: ghc -O2 Main.hs -o nn && ./nn
--
-- HOW IT WORKS
-- ------------
-- Network: nIn -> nHidden (sigmoid) -> nOut (sigmoid), trained by SGD on MSE.
--
-- FORWARD   hidden[j] = sigmoid(b1[j] + sum_i x[i] * w1[i*nHid + j])
--           out[k]    = sigmoid(b2[k] + sum_j hidden[j] * w2[j*nOut + k])
--           sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)
--
-- BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
--           d_out[k]    = (out[k] - y[k]) * out[k] * (1 - out[k])
--           d_hidden[j] = (sum_k d_out[k] * w2[j*nOut+k]) * h[j] * (1 - h[j])
--
-- UPDATE    every gradient = delta * activation feeding that edge:
--           w2[j][k] -= lr * d_out[k] * hidden[j]    b2[k] -= lr * d_out[k]
--           w1[i][j] -= lr * d_hidden[j] * x[i]      b1[j] -= lr * d_hidden[j]
--
-- Replace the "toy dataset" block in main with real data to train on it.

{-# LANGUAGE BangPatterns #-}

module Main (main) where

import Control.Monad (foldM, foldM_, forM_, when)
import Control.Monad.ST (runST)
import Data.Array.ST (freeze, newListArray, readArray, thaw, writeArray)
import Data.Array.Unboxed (UArray, listArray, (!))
import Data.Bits (shiftR)
import Data.Word (Word64)
import Text.Printf (printf)

-- | Deterministic SplitMix64 PRNG ('System.Random' is not in @base@).
newtype Seed = Seed Word64

nextUniform :: Seed -> (Double, Seed)
nextUniform (Seed s) =
  let s'   = s * 6364136223846793005 + 1442695040888963407
      frac = fromIntegral (s' `shiftR` 11) / 9007199254740992
  in (frac, Seed s')

-- | @n@ Box-Muller standard normals, threading the seed.
normals :: Int -> Seed -> ([Double], Seed)
normals n = go n []
  where
    go 0 acc s = (reverse acc, s)
    go k acc s =
      let (u, s1) = nextUniform s
          u'      = max u 1e-12
          (v, s2) = nextUniform s1
      in go (k - 1) (sqrt (-2 * log u') * cos (2 * pi * v) : acc) s2

data Net = Net
  { lr   :: !Double              -- strict fields: no space leaks, no thunks
  , nIn  :: !Int
  , nHid :: !Int
  , nOut :: !Int
  , w1   :: !(UArray Int Double) -- flat, row-major
  , b1   :: !(UArray Int Double)
  , w2   :: !(UArray Int Double)
  , b2   :: !(UArray Int Double)
  }

initNet :: Int -> Int -> Int -> Double -> Seed -> Net
initNet nIn nHid nOut rate seed =
  let (g1, s1) = normals (nIn * nHid) seed
      (g2, _)  = normals (nHid * nOut) s1
      scale m  = sqrt (2 / fromIntegral m)
      he g m n = listArray (0, m * n - 1) (map (* scale m) g)
      zeros k  = listArray (0, k - 1) (replicate k 0)
  in Net rate nIn nHid nOut (he g1 nIn nHid) (zeros nHid) (he g2 nHid nOut) (zeros nOut)

-- | One epoch of per-sample SGD. Pure API; inside @runST@ the weights are
-- unboxed mutable arrays, thawed once and frozen back afterwards.
trainEpoch :: Net -> [(UArray Int Double, UArray Int Double)] -> (Double, Net)
trainEpoch net0 dataset = runST $ do
  let nI = nIn net0
      nH = nHid net0
      nO = nOut net0
      rate = lr net0
      sigmoid x = 1 / (1 + exp (negate x))
  w1m <- thaw (w1 net0)
  b1m <- thaw (b1 net0)
  w2m <- thaw (w2 net0)
  b2m <- thaw (b2 net0)
  hidden <- newListArray (0, nH - 1) (replicate nH 0)
  out    <- newListArray (0, nO - 1) (replicate nO 0)
  dOut   <- newListArray (0, nO - 1) (replicate nO 0)
  dHid   <- newListArray (0, nH - 1) (replicate nH 0)

  let forwardSample x = do
        forM_ [0 .. nH - 1] $ \j -> do
          z0 <- readArray b1m j
          z <- foldM (\acc i -> do
                        w <- readArray w1m (i * nH + j)
                        pure (acc + (x ! i) * w)) z0 [0 .. nI - 1]
          writeArray hidden j (sigmoid z)
        forM_ [0 .. nO - 1] $ \k -> do
          z0 <- readArray b2m k
          z <- foldM (\acc j -> do
                        h <- readArray hidden j
                        w <- readArray w2m (j * nO + k)
                        pure (acc + h * w)) z0 [0 .. nH - 1]
          writeArray out k (sigmoid z)

      step !acc (x, y) = do
        forwardSample x

        -- Output delta: error times sigmoid'(out).
        forM_ [0 .. nO - 1] $ \k -> do
          o <- readArray out k
          let t = y ! k
          writeArray dOut k ((o - t) * o * (1 - o))

        -- Hidden delta: backpropagated error times sigmoid'(hidden).
        forM_ [0 .. nH - 1] $ \j -> do
          back <- foldM (\a k -> do
                           d <- readArray dOut k
                           w <- readArray w2m (j * nO + k)
                           pure (a + d * w)) 0 [0 .. nO - 1]
          a <- readArray hidden j
          writeArray dHid j (back * a * (1 - a))

        -- Gradient descent: weight -= lr * delta * activation on that edge.
        forM_ [0 .. nH - 1] $ \j ->
          forM_ [0 .. nO - 1] $ \k -> do
            d <- readArray dOut k
            h <- readArray hidden j
            w <- readArray w2m (j * nO + k)
            writeArray w2m (j * nO + k) (w - rate * d * h)
        forM_ [0 .. nO - 1] $ \k -> do
          d <- readArray dOut k
          b <- readArray b2m k
          writeArray b2m k (b - rate * d)
        forM_ [0 .. nI - 1] $ \i ->
          forM_ [0 .. nH - 1] $ \j -> do
            d <- readArray dHid j
            w <- readArray w1m (i * nH + j)
            writeArray w1m (i * nH + j) (w - rate * d * (x ! i))
        forM_ [0 .. nH - 1] $ \j -> do
          d <- readArray dHid j
          b <- readArray b1m j
          writeArray b1m j (b - rate * d)

        foldM (\a k -> do
                 o <- readArray out k
                 let t = y ! k
                     d = o - t
                 pure (a + d * d)) (0 :: Double) [0 .. nO - 1]

  total <- foldM step 0 dataset
  w1' <- freeze w1m
  b1' <- freeze b1m
  w2' <- freeze w2m
  b2' <- freeze b2m
  pure ( total / fromIntegral (length dataset)
       , net0 { w1 = w1', b1 = b1', w2 = w2', b2 = b2' } )

genSamples :: Int -> Int -> Seed -> ([UArray Int Double], Seed)
genSamples count dim s0 = go count [] s0
  where
    go 0 acc s = (reverse acc, s)
    go k acc s =
      let (vals, s') = normals dim s
      in go (k - 1) (listArray (0, dim - 1) vals : acc) s'

main :: IO ()
main = do
  let nI     = __INPUT__
      nH     = __HIDDEN__
      nO     = __OUTPUT__
      rate   = __LR__
      epochs = __EPOCHS__ :: Int
      showEvery = max (epochs `div` 10) 1

      -- Toy dataset — replace with your own.
      (xs, s1) = genSamples 64 nI (Seed 7)
      (ys, _)  = genSamples 64 nO s1
      dataset  = zip xs ys

      net0 = initNet nI nH nO rate (Seed 42)

      step net epoch = do
        let (mse, net') = trainEpoch net dataset
        when (epoch `mod` showEvery == 0) $           printf "epoch %5d  mse = %.6f\n" epoch mse
        pure net'

  foldM_ step net0 [1 .. epochs]
EOF
    fill_placeholders "$f"
    add_file "$OUTPUT_DIR/haskell/Main.hs"
}

gen_r() {
    mkdir -p "$OUTPUT_DIR/r"
    local f="$OUTPUT_DIR/r/neural_network.R"
    cat > "$f" <<'EOF'
# neural_network.R — idiomatic R: S3 class with print/predict methods,
# vectorised base, stopifnot validation. No packages required.
# Run: Rscript neural_network.R
#
# HOW IT WORKS
# ------------
# Network: n_in -> n_hidden (sigmoid) -> n_out (sigmoid), trained by
# full-batch SGD on mean squared error.
#
# FORWARD   hidden = sigmoid(X %*% W1 + b1)        (whole-batch matrices)
#           out    = sigmoid(hidden %*% W2 + b2)
#           sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)
#
# BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
#           delta2 = (out - y) * out * (1 - out)
#           delta1 = (delta2 %*% t(W2)) * hidden * (1 - hidden)
#
# UPDATE    gradients via crossprod() (= t(A) %*% B), averaged over batch:
#           W2 -= lr * crossprod(hidden, delta2)/m     b2 -= lr * colMeans(delta2)
#           W1 -= lr * crossprod(X, delta1)/m          b1 -= lr * colMeans(delta1)
#
# Replace the "toy dataset" block at the bottom with real data to train on it.

set.seed(42)

sigmoid <- function(z) 1 / (1 + exp(-z))

# --- constructor ------------------------------------------------------

new_neural_network <- function(n_in, n_hidden, n_out, learning_rate) {
  stopifnot(n_in > 0, n_hidden > 0, n_out > 0, learning_rate > 0)
  structure(
    list(
      n_in = n_in,
      n_hidden = n_hidden,
      n_out = n_out,
      learning_rate = learning_rate,
      # He-style init: sd = sqrt(2/fan_in) keeps activations healthy.
      W1 = matrix(rnorm(n_in * n_hidden, sd = sqrt(2 / n_in)), nrow = n_in),
      b1 = rep(0, n_hidden),
      W2 = matrix(rnorm(n_hidden * n_out, sd = sqrt(2 / n_hidden)), nrow = n_hidden),
      b2 = rep(0, n_out)
    ),
    class = "neural_network"
  )
}

# --- S3 methods -------------------------------------------------------

# Show the architecture instead of dumping four matrices.
print.neural_network <- function(x, ...) {
  cat(sprintf(
    "<neural_network> %d -> %d (sigmoid) -> %d, lr = %g\n",
    x$n_in, x$n_hidden, x$n_out, x$learning_rate
  ))
  invisible(x)
}

# Predict for new data (rows = observations).
predict.neural_network <- function(object, newdata, ...) {
  stopifnot(ncol(newdata) == object$n_in)
  hidden <- sigmoid(sweep(newdata %*% object$W1, 2, object$b1, "+"))
  sigmoid(sweep(hidden %*% object$W2, 2, object$b2, "+"))
}

# --- training ---------------------------------------------------------

# One full-batch SGD step; returns the updated network.
sgd_step <- function(object, X, y) {
  hidden <- sigmoid(sweep(X %*% object$W1, 2, object$b1, "+"))
  out <- sigmoid(sweep(hidden %*% object$W2, 2, object$b2, "+"))
  m <- nrow(X)

  delta2 <- (out - y) * out * (1 - out)
  delta1 <- (delta2 %*% t(object$W2)) * hidden * (1 - hidden)

  object$W2 <- object$W2 - object$learning_rate * crossprod(hidden, delta2) / m
  object$b2 <- object$b2 - object$learning_rate * colMeans(delta2)
  object$W1 <- object$W1 - object$learning_rate * crossprod(X, delta1) / m
  object$b1 <- object$b1 - object$learning_rate * colMeans(delta1)
  object
}

# Train with full-batch SGD; returns the fitted network.
train <- function(object, X, y, epochs = 1000, verbose = TRUE) {
  stopifnot(inherits(object, "neural_network"), ncol(X) == object$n_in)
  show_every <- max(epochs %/% 10, 1)
  for (epoch in seq_len(epochs)) {
    object <- sgd_step(object, X, y)
    if (verbose && epoch %% show_every == 0) {
      mse <- mean((predict(object, X) - y)^2)   # reuses the S3 predict method
      cat(sprintf("epoch %5d  mse = %.6f\n", epoch, mse))
    }
  }
  object
}

# ---- demo (replace with your own data) ----------------------------------
n_in <- __INPUT__
n_hidden <- __HIDDEN__
n_out <- __OUTPUT__

net <- new_neural_network(n_in, n_hidden, n_out, learning_rate = __LR__)
print(net)

X <- matrix(runif(64 * n_in), nrow = 64)
y <- matrix(runif(64 * n_out), nrow = 64)

net <- train(net, X, y, epochs = __EPOCHS__)

print(round(predict(net, head(X, 5)), 3))
EOF
    fill_placeholders "$f"
    chmod +x "$f"
    add_file "$OUTPUT_DIR/r/neural_network.R"
}

gen_julia() {
    mkdir -p "$OUTPUT_DIR/julia"
    local f="$OUTPUT_DIR/julia/neural_network.jl"
    cat > "$f" <<'EOF'
# neural_network.jl — idiomatic Julia: concrete parametrized struct,
# Random.Xoshiro, docstrings, Logging (@info), Base.show, unicode gradients.
# Run: julia neural_network.jl   (Julia 1.7+)
#
# HOW IT WORKS
# ------------
# Network: n_in -> n_hidden (sigmoid) -> n_out (sigmoid), trained by
# full-batch SGD on mean squared error.
#
# FORWARD   hidden = sigmoid.(X * W1 .+ b1')      (whole-batch broadcasting)
#           out    = sigmoid.(hidden * W2 .+ b2')
#           sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)
#
# BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
#           δ2 = (out .- y) .* out .* (1 .- out)
#           δ1 = (δ2 * W2') .* hidden .* (1 .- hidden)
#
# UPDATE    gradients via transposed matmuls, averaged over the batch:
#           W2 .-= lr .* (hidden' * δ2) ./ m     b2 .-= lr .* vec(sum(δ2, dims=1)) ./ m
#           W1 .-= lr .* (X' * δ1) ./ m          b1 .-= lr .* vec(sum(δ1, dims=1)) ./ m
#
# Replace the "toy dataset" block at the bottom with real data to train on it.

using Random, Logging

"Elementwise logistic activation."
sigmoid(x) = 1 / (1 + exp(-x))

"""
    NeuralNetwork(n_in, n_hidden, n_out, lr; rng = Random.Xoshiro(42))

A one-hidden-layer MLP with sigmoid activations and He-initialised weights.
Type parameters keep the struct concrete — no abstract-typed fields.
"""
struct NeuralNetwork{M1,V1,M2,V2}
    lr::Float64
    W1::M1
    b1::V1
    W2::M2
    b2::V2
end

function NeuralNetwork(n_in::Int, n_hidden::Int, n_out::Int, lr::Real;
                       rng::AbstractRNG = Random.Xoshiro(42))
    NeuralNetwork(
        Float64(lr),
        randn(rng, n_in, n_hidden) .* sqrt(2 / n_in),
        zeros(n_hidden),
        randn(rng, n_hidden, n_out) .* sqrt(2 / n_hidden),
        zeros(n_out),
    )
end

"Human-readable summary via the display system."
function Base.show(io::IO, ::MIME"text/plain", net::NeuralNetwork)
    print(io, "NeuralNetwork($(size(net.W1, 1)) → $(size(net.W1, 2)) → ",
          "$(size(net.W2, 2)), lr = $(net.lr))")
end

"Forward pass for a batch `X` (rows = observations); returns the output matrix."
forward(net::NeuralNetwork, X::AbstractMatrix) =
    sigmoid.(sigmoid.(X * net.W1 .+ net.b1') * net.W2 .+ net.b2')

"""
    train!(net; X, y, epochs = 1000, show_every = max(epochs ÷ 10, 1))

Full-batch SGD, mutating `net` in place (the `!` convention).
"""
function train!(net::NeuralNetwork; X, y, epochs::Integer = 1000,
                show_every = max(epochs ÷ 10, 1))
    m = size(X, 1)
    for epoch in 1:epochs
        hidden = sigmoid.(X * net.W1 .+ net.b1')
        out = sigmoid.(hidden * net.W2 .+ net.b2')

        # Deltas per the chain rule (δ = error signal per layer).
        δ2 = (out .- y) .* out .* (1 .- out)
        δ1 = (δ2 * net.W2') .* hidden .* (1 .- hidden)

        # Gradient descent with transposed matmuls as outer products.
        net.W2 .-= net.lr .* (hidden' * δ2) ./ m
        net.b2 .-= net.lr .* vec(sum(δ2; dims = 1)) ./ m
        net.W1 .-= net.lr .* (X' * δ1) ./ m
        net.b1 .-= net.lr .* vec(sum(δ1; dims = 1)) ./ m

        epoch % show_every == 0 && @info "training" epoch mse = sum(abs2, out .- y) / length(y)
    end
    return net
end

# ---- demo (replace with your own data) ----------------------------------
const N_IN, N_HIDDEN, N_OUT = __INPUT__, __HIDDEN__, __OUTPUT__
const LEARNING_RATE, EPOCHS = __LR__, __EPOCHS__

data_rng = Random.Xoshiro(7)          # explicit local RNG — no global seed
X = rand(data_rng, 64, N_IN)
y = rand(data_rng, 64, N_OUT)

net = NeuralNetwork(N_IN, N_HIDDEN, N_OUT, LEARNING_RATE)
display(net)
train!(net; X, y, epochs = EPOCHS)

println("\nfirst 5 predictions:")
display(round.(forward(net, X[1:5, :]); digits = 3))
EOF
    fill_placeholders "$f"
    chmod +x "$f"
    add_file "$OUTPUT_DIR/julia/neural_network.jl"
}

gen_scala() {
    mkdir -p "$OUTPUT_DIR/scala"
    local f="$OUTPUT_DIR/scala/NeuralNetwork.scala"
    cat > "$f" <<'EOF'
//> using scala 3.3.3

// NeuralNetwork.scala — idiomatic Scala 3: case classes with require(),
// significant indentation, top-level extension methods, Array.tabulate,
// @main entry point, f-interpolator. Run: scala-cli run NeuralNetwork.scala
//
// HOW IT WORKS
// ------------
// Network: nIn -> nHidden (sigmoid) -> nOut (sigmoid), trained by SGD on MSE.
//
// FORWARD   hidden[j] = sigmoid(b1(j) + sum_i x(i) * w1(i)(j))
//           out[k]    = sigmoid(b2(k) + sum_j hidden(j) * w2(j)(k))
//           sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)
//
// BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
//           dOut(k)    = (out(k) - y(k)) * out(k) * (1 - out(k))
//           dHidden(j) = (sum_k dOut(k) * w2(j)(k)) * hidden(j) * (1 - hidden(j))
//
// UPDATE    every gradient = delta * activation feeding that edge:
//           w2(j)(k) -= lr * dOut(k) * hidden(j)     b2(k) -= lr * dOut(k)
//           w1(i)(j) -= lr * dHidden(j) * x(i)       b1(j) -= lr * dHidden(j)
//
// Replace the "toy dataset" block in demo() with real data to train on it.

import scala.util.Random

/** Hyperparameters, validated at construction. */
final case class HyperParams(nIn: Int, nHidden: Int, nOut: Int, lr: Double, epochs: Int):
  require(nIn > 0 && nHidden > 0 && nOut > 0, "layer sizes must be positive")
  require(lr > 0, "learning rate must be positive")

extension (v: Array[Double])
  /** v · w[:, col] — a column of a row-major matrix. */
  def dotCol(w: Array[Array[Double]], col: Int): Double =
    v.indices.foldLeft(0.0)((acc, i) => acc + v(i) * w(i)(col))

/** One-hidden-layer MLP trained with per-sample SGD. */
final class NeuralNetwork(hp: HyperParams, seed: Long = 42L):
  private val nIn = hp.nIn
  private val nHidden = hp.nHidden
  private val nOut = hp.nOut
  private val lr = hp.lr
  private val rng = Random(seed)

  private val w1 = heMatrix(nIn, nHidden)     // He-style init
  private val b1 = Array.fill(nHidden)(0.0)
  private val w2 = heMatrix(nHidden, nOut)
  private val b2 = Array.fill(nOut)(0.0)
  private var hidden: Array[Double] = Array.empty

  private def heMatrix(rows: Int, cols: Int): Array[Array[Double]] =
    val scale = math.sqrt(2.0 / rows)
    Array.tabulate(rows, cols)((_, _) => rng.nextGaussian() * scale)

  /** Forward pass; caches hidden activations for trainStep. */
  def forward(x: Array[Double]): Array[Double] =
    hidden = Array.tabulate(nHidden)(j => sigmoid(b1(j) + x.dotCol(w1, j)))
    Array.tabulate(nOut)(k => sigmoid(b2(k) + hidden.dotCol(w2, k)))

  /** One SGD step; returns the sample's squared error. */
  def trainStep(x: Array[Double], y: Array[Double]): Double =
    val out = forward(x)

    // Output delta: error times sigmoid'(out).
    val dOut = (out zip y).map { case (o, t) => (o - t) * o * (1 - o) }
    // Hidden delta: backpropagated error times sigmoid'(hidden).
    val dHidden = Array.tabulate(nHidden) { j =>
      val back = dOut.zip(w2(j)).map(_ * _).sum
      back * hidden(j) * (1 - hidden(j))
    }

    // Gradient descent: weight -= lr * delta * activation on that edge.
    for j <- w2.indices; k <- dOut.indices do w2(j)(k) -= lr * dOut(k) * hidden(j)
    for k <- b2.indices do b2(k) -= lr * dOut(k)
    for i <- w1.indices; j <- dHidden.indices do w1(i)(j) -= lr * dHidden(j) * x(i)
    for j <- b1.indices do b1(j) -= lr * dHidden(j)

    (out zip y).map { case (o, t) => val d = o - t; d * d }.sum

  private def sigmoid(z: Double): Double = 1.0 / (1.0 + math.exp(-z))

@main def demo(): Unit =
  val hp = HyperParams(nIn = __INPUT__, nHidden = __HIDDEN__, nOut = __OUTPUT__,
                       lr = __LR__, epochs = __EPOCHS__)
  val net = NeuralNetwork(hp)

  val data = Random(7)  // toy dataset — replace with your own
  val dataset = List.fill(64):
    (Array.fill(hp.nIn)(data.nextDouble()),
     Array.fill(hp.nOut)(data.nextDouble()))

  val showEvery = math.max(hp.epochs / 10, 1)
  for epoch <- 1 to hp.epochs do
    val loss = dataset.map((x, y) => net.trainStep(x, y)).sum
    if epoch % showEvery == 0 then
      println(f"epoch $epoch%5d  mse = ${loss / dataset.size}%.6f")
EOF
    fill_placeholders "$f"
    add_file "$OUTPUT_DIR/scala/NeuralNetwork.scala"
}

gen_fsharp() {
    mkdir -p "$OUTPUT_DIR/fsharp"
    local f="$OUTPUT_DIR/fsharp/neural_network.fsx"
    cat > "$f" <<'EOF'
// neural_network.fsx — idiomatic F#: module of pure functions, records with
// functional updates ({ net with ... }), pipelines, Array combinators.
// Run: dotnet fsi neural_network.fsx        (.NET 6+ / F# 6+)
//
// HOW IT WORKS
// ------------
// Network: NIn -> NHidden (sigmoid) -> NOut (sigmoid), trained by SGD on MSE.
//
// FORWARD   hidden[j] = sigmoid(B1[j] + sum_i x[i] * W1[i,j])
//           out[k]    = sigmoid(B2[k] + sum_j hidden[j] * W2[j,k])
//           sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)
//
// BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
//           dOut[k]    = (out[k] - y[k]) * out[k] * (1 - out[k])
//           dHidden[j] = (sum_k dOut[k] * W2[j,k]) * hidden[j] * (1 - hidden[j])
//
// UPDATE    every gradient = delta * activation feeding that edge:
//           W2[j,k] -= lr * dOut[k] * hidden[j]     B2[k] -= lr * dOut[k]
//           W1[i,j] -= lr * dHidden[j] * x[i]       B1[j] -= lr * dHidden[j]
//
// Replace the "toy dataset" block at the bottom with real data to train on it.

module Neural

let sigmoid (z: float) : float = 1.0 / (1.0 + exp -z)

type Hyper = { NIn: int; NHidden: int; NOut: int; Lr: float }

type Net =
    { Hyper: Hyper
      W1: float[,]
      B1: float[]
      W2: float[,]
      B2: float[]
      mutable Hidden: float[] }   // cache for backprop; contents replaced per step

let private gauss (rng: System.Random) =
    let rec loop () =
        let u = rng.NextDouble()
        if u = 0.0 then loop () else u
    sqrt (-2.0 * log (loop ())) * cos (2.0 * System.Math.PI * rng.NextDouble())

let init (hyper: Hyper) (rng: System.Random) : Net =
    let he rows cols =
        let scale = sqrt (2.0 / float rows)
        Array2D.init rows cols (fun _ _ -> gauss rng * scale)
    { Hyper = hyper
      W1 = he hyper.NIn hyper.NHidden
      B1 = Array.zeroCreate hyper.NHidden
      W2 = he hyper.NHidden hyper.NOut
      B2 = Array.zeroCreate hyper.NOut
      Hidden = Array.zeroCreate hyper.NHidden }

let private dotCol v w col =
    Array.sumBy (fun i -> v[i] * w[i, col]) [| 0 .. Array2D.length1 w - 1 |]

let forward (net: Net) (x: float[]) : float[] * float[] =
    let hidden =
        Array.init net.Hyper.NHidden (fun j ->
            sigmoid (net.B1[j] + dotCol x net.W1 j))
    let out =
        Array.init net.Hyper.NOut (fun k ->
            sigmoid (net.B2[k] + dotCol hidden net.W2 k))
    net.Hidden <- hidden
    hidden, out

/// One SGD step; returns (squared error, updated net) — pure at the API level.
let step (net: Net) (x: float[]) (y: float[]) : float * Net =
    let hidden, out = forward net x

    let dOut = Array.map2 (fun o t -> (o - t) * o * (1.0 - o)) out y
    let dHid =
        Array.init net.Hyper.NHidden (fun j ->
            let back = Array.sumBy (fun k -> dOut[k] * net.W2[j, k]) [| 0 .. net.Hyper.NOut - 1 |]
            back * hidden[j] * (1.0 - hidden[j]))

    let lr = net.Hyper.Lr
    let w2' = Array2D.init net.Hyper.NHidden net.Hyper.NOut
                (fun j k -> net.W2[j, k] - lr * dOut[k] * hidden[j])
    let w1' = Array2D.init net.Hyper.NIn net.Hyper.NHidden
                (fun i j -> net.W1[i, j] - lr * dHid[j] * x[i])
    let b2' = Array.mapi2 (fun k b d -> b - lr * d) net.B2 dOut
    let b1' = Array.mapi2 (fun j b d -> b - lr * d) net.B1 dHid

    let sqErr =
        Array.map2 (fun o t -> let d = o - t in d * d) out y |> Array.sum
    sqErr, { net with W1 = w1'; B1 = b1'; W2 = w2'; B2 = b2' }

/// One epoch; returns (mean squared error, updated net) via a left fold.
let epoch (net: Net) (dataset: (float[] * float[])[]) : float * Net =
    dataset
    |> Array.fold (fun (total, n) (x, y) ->
            let err, n' = step n x y
            total + err, n') (0.0, net)
    |> fun (total, n) -> total / float (Array.length dataset), n

// ---- demo (replace with your own data) ------------------------------
open Neural

let hyper = { NIn = __INPUT__; NHidden = __HIDDEN__; NOut = __OUTPUT__; Lr = __LR__ }
let epochs = __EPOCHS__

let net0 = init hyper (System.Random 42)

let data = System.Random 7
let dataset =
    Array.init 64 (fun _ ->
        Array.init hyper.NIn (fun _ -> data.NextDouble()),
        Array.init hyper.NOut (fun _ -> data.NextDouble()))

let showEvery = max (epochs / 10) 1

let rec run (net: Net) epoch =
    if epoch > epochs then net
    else
        let loss, net' = epoch net dataset
        if epoch % showEvery = 0 then
            printfn "epoch %5d  mse = %.6f" epoch loss
        run net' (epoch + 1)

let _finalNet = run net0 1
EOF
    fill_placeholders "$f"
    add_file "$OUTPUT_DIR/fsharp/neural_network.fsx"
}

gen_nim() {
    mkdir -p "$OUTPUT_DIR/nim"
    local f="$OUTPUT_DIR/nim/neural_network.nim"
    cat > "$f" <<'EOF'
## neural_network.nim — idiomatic Nim: std/random gauss, sugar.collect
## comprehensions, openArray params, `result`, strformat.
## Run:
##   nim c -d:release -o:nn neural_network.nim && ./nn    (Nim 1.6+)
##
## HOW IT WORKS
## ------------
## Network: nIn -> nHidden (sigmoid) -> nOut (sigmoid), trained by SGD on MSE.
##
## FORWARD   hidden[j] = sigmoid(b1[j] + sum_i x[i] * w1[i][j])
##           output[k] = sigmoid(b2[k] + sum_j hidden[j] * w2[j][k])
##           sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)
##
## BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
##           dOut[k]    = (output[k] - y[k]) * output[k] * (1 - output[k])
##           dHidden[j] = (sum_k dOut[k] * w2[j][k]) * hidden[j] * (1 - hidden[j])
##
## UPDATE    every gradient = delta * activation feeding that edge:
##           w2[j][k] -= lr * dOut[k] * hidden[j]     b2[k] -= lr * dOut[k]
##           w1[i][j] -= lr * dHidden[j] * x[i]       b1[j] -= lr * dHidden[j]
##
## Replace the "toy dataset" block at the bottom with real data to train on it.

import std/[math, random, sequtils, strformat, sugar]

type
  HyperParams = object
    nIn, nHidden, nOut: int
    lr: float

  Mlp = object
    hp: HyperParams
    w1, w2: seq[seq[float]]
    b1, b2, hidden: seq[float]

func sigmoid(x: float): float {.inline.} = 1.0 / (1.0 + exp(-x))

func dot(a, b: openArray[float]): float {.inline.} =
  sum(mapIt(0 ..< a.len, a[it] * b[it]))

proc heMatrix(rows, cols: int): seq[seq[float]] =
  ## He-initialised weights; std/random already seeded by the caller.
  let scale = sqrt(2.0 / rows.toFloat)
  collect(newSeq):
    for _ in 0 ..< rows:
      collect(newSeq):
        for _ in 0 ..< cols:
          gauss() * scale

proc newMlp(hp: HyperParams, seed: int64): Mlp =
  randomize(seed)
  Mlp(
    hp: hp,
    w1: heMatrix(hp.nIn, hp.nHidden),
    b1: newSeq[float](hp.nHidden),
    w2: heMatrix(hp.nHidden, hp.nOut),
    b2: newSeq[float](hp.nOut),
    hidden: newSeq[float](hp.nHidden))

proc forward(m: var Mlp, x: openArray[float]): seq[float] =
  for j in 0 ..< m.hp.nHidden:
    var z = m.b1[j]
    for i in 0 ..< m.hp.nIn:
      z += x[i] * m.w1[i][j]
    m.hidden[j] = sigmoid(z)
  for k in 0 ..< m.hp.nOut:
    var z = m.b2[k]
    for j in 0 ..< m.hp.nHidden:
      z += m.hidden[j] * m.w2[j][k]
    result.add sigmoid(z)          # the classic `result` idiom

proc trainStep(m: var Mlp, x, y: openArray[float]): float =
  let output = forward(m, x)

  # Output delta: error times sigmoid'(out).
  let dOut = collect(newSeq):
    for k in 0 ..< m.hp.nOut:
      (output[k] - y[k]) * output[k] * (1.0 - output[k])

  # Hidden delta: backpropagated error times sigmoid'(hidden).
  let dHidden = collect(newSeq):
    for j in 0 ..< m.hp.nHidden:
      dot(dOut, m.w2[j]) * m.hidden[j] * (1.0 - m.hidden[j])

  # Gradient descent: weight -= lr * delta * activation on that edge.
  for j in 0 ..< m.hp.nHidden:
    for k in 0 ..< m.hp.nOut:
      m.w2[j][k] -= m.hp.lr * dOut[k] * m.hidden[j]
  for k in 0 ..< m.hp.nOut:
    m.b2[k] -= m.hp.lr * dOut[k]
  for i in 0 ..< m.hp.nIn:
    for j in 0 ..< m.hp.nHidden:
      m.w1[i][j] -= m.hp.lr * dHidden[j] * x[i]
  for j in 0 ..< m.hp.nHidden:
    m.b1[j] -= m.hp.lr * dHidden[j]

  let sq = collect(newSeq):
    for k in 0 ..< m.hp.nOut:
      let d = output[k] - y[k]
      d * d
  sum(sq)

when isMainModule:
  let hp = HyperParams(nIn: __INPUT__, nHidden: __HIDDEN__,
                       nOut: __OUTPUT__, lr: __LR__)
  let epochs = __EPOCHS__
  var net = newMlp(hp, seed = 42)

  randomize(7)  # toy dataset — replace with your own
  let xs = collect(newSeq):
    for _ in 0 ..< 64:
      collect(newSeq):
        for _ in 0 ..< hp.nIn: rand(1.0)
  let ys = collect(newSeq):
    for _ in 0 ..< 64:
      collect(newSeq):
        for _ in 0 ..< hp.nOut: rand(1.0)
  let dataset = zip(xs, ys)

  let showEvery = max(epochs div 10, 1)
  for epoch in 1 .. epochs:
    var loss = 0.0
    for (x, y) in dataset:
      loss += net.trainStep(x, y)
    if epoch mod showEvery == 0:
      let mse = loss / dataset.len.toFloat
      echo &"epoch {epoch:5}  mse = {mse:.6f}"
EOF
    fill_placeholders "$f"
    add_file "$OUTPUT_DIR/nim/neural_network.nim"
}

gen_zig() {
    mkdir -p "$OUTPUT_DIR/zig"
    local f="$OUTPUT_DIR/zig/neural_network.zig"
    cat > "$f" <<'EOF'
//! neural_network.zig — idiomatic Zig: a comptime-generic function that
//! returns a type (layer sizes become part of the type), std.Random.Xoshiro,
//! defer for cleanup, @-builtins. Build (Zig 0.12-0.13):
//!   zig build-exe neural_network.zig -O ReleaseFast && ./neural_network
//!
//! HOW IT WORKS
//! ------------
//! Network: n_in -> n_hidden (sigmoid) -> n_out (sigmoid), trained by SGD
//! on mean squared error.
//!
//! FORWARD   hidden[j] = sigmoid(b1[j] + sum_i x[i] * w1[i][j])
//!           out[k]    = sigmoid(b2[k] + sum_j hidden[j] * w2[j][k])
//!           sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)
//!
//! BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
//!           d_out[k]    = (out[k] - y[k]) * out[k] * (1 - out[k])
//!           d_hidden[j] = (sum_k d_out[k] * w2[j][k]) * hidden[j] * (1 - hidden[j])
//!
//! UPDATE    every gradient = delta * activation feeding that edge:
//!           w2[j][k] -= lr * d_out[k] * hidden[j]    b2[k] -= lr * d_out[k]
//!           w1[i][j] -= lr * d_hidden[j] * x[i]      b1[j] -= lr * d_hidden[j]
//!
//! Replace the "toy dataset" block in main() with real data to train on it.

const std = @import("std");

fn sigmoid(x: f64) f64 {
    return 1.0 / (1.0 + @exp(-x));
}

/// Box-Muller standard normal on top of the std Random interface.
fn gauss(rng: std.Random) f64 {
    var u = rng.float(f64);
    while (u == 0.0) u = rng.float(f64);
    const v = rng.float(f64);
    return @sqrt(-2.0 * @log(u)) * @cos(2.0 * std.math.pi * v);
}

/// The classic Zig pattern: a function parameterised at compile time that
/// returns a struct type. n_in/n_hidden/n_out are part of the type itself.
fn Mlp(comptime n_in: usize, comptime n_hidden: usize, comptime n_out: usize) type {
    return struct {
        const Self = @This();

        lr: f64,
        w1: [n_in][n_hidden]f64,
        b1: [n_hidden]f64,
        w2: [n_hidden][n_out]f64,
        b2: [n_out]f64,
        hidden: [n_hidden]f64 = undefined,

        fn init(lr: f64, rng: std.Random) Self {
            var self = Self{
                .lr = lr,
                .w1 = undefined,
                .b1 = [_]f64{0} ** n_hidden,
                .w2 = undefined,
                .b2 = [_]f64{0} ** n_out,
            };
            for (&self.w1) |*row| initRow(row, 2.0 / n_in, rng);
            for (&self.w2) |*row| initRow(row, 2.0 / n_hidden, rng);
            return self;
        }

        fn initRow(row: []f64, inv: f64, rng: std.Random) void {
            for (row) |*w| w.* = gauss(rng) * @sqrt(inv);   // He-style init
        }

        /// Forward pass; caches hidden activations for trainStep.
        fn forward(self: *Self, x: *const [n_in]f64) [n_out]f64 {
            for (0..n_hidden) |j| {
                var z = self.b1[j];
                for (x, 0..) |xi, i| z += xi * self.w1[i][j];
                self.hidden[j] = sigmoid(z);
            }
            var out: [n_out]f64 = undefined;
            for (0..n_out) |k| {
                var z = self.b2[k];
                for (self.hidden, 0..) |h, j| z += h * self.w2[j][k];
                out[k] = sigmoid(z);
            }
            return out;
        }

        /// One SGD step; returns the sample's squared error.
        fn trainStep(self: *Self, x: *const [n_in]f64, y: *const [n_out]f64) f64 {
            const out = self.forward(x);

            var d_out: [n_out]f64 = undefined;
            var sq_err: f64 = 0.0;
            for (0..n_out) |k| {
                const d = out[k] - y[k];
                d_out[k] = d * out[k] * (1.0 - out[k]);   // error * sigmoid'(out)
                sq_err += d * d;
            }

            var d_hidden: [n_hidden]f64 = undefined;
            for (0..n_hidden) |j| {
                var back: f64 = 0.0;
                for (d_out, 0..) |d, k| back += d * self.w2[j][k];
                d_hidden[j] = back * self.hidden[j] * (1.0 - self.hidden[j]);
            }

            for (0..n_hidden) |j| {
                for (0..n_out) |k| self.w2[j][k] -= self.lr * d_out[k] * self.hidden[j];
            }
            for (0..n_out) |k| self.b2[k] -= self.lr * d_out[k];
            for (0..n_in) |i| {
                for (0..n_hidden) |j| self.w1[i][j] -= self.lr * d_hidden[j] * x[i];
            }
            for (0..n_hidden) |j| self.b1[j] -= self.lr * d_hidden[j];
            return sq_err;
        }
    };
}

pub fn main() !void {
    // The one mandatory Zig idiom: an explicit allocator, released via defer.
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    const n_in = __INPUT__;
    const n_hidden = __HIDDEN__;
    const n_out = __OUTPUT__;
    const lr = __LR__;
    const epochs = __EPOCHS__;

    var prng = std.Random.Xoshiro.init(42);
    const rng = prng.random();

    var net = Mlp(n_in, n_hidden, n_out).init(lr, rng);

    // Toy dataset — replace with your own.
    const Sample = struct { x: [n_in]f64, y: [n_out]f64 };
    var data_prng = std.Random.Xoshiro.init(7);
    const data = data_prng.random();

    const dataset = try allocator.alloc(Sample, 64);
    defer allocator.free(dataset);
    for (dataset) |*s| {
        for (&s.x) |*v| v.* = data.float(f64);
        for (&s.y) |*v| v.* = data.float(f64);
    }

    const show_every = @max(epochs / 10, 1);
    const stdout = std.io.getStdOut().writer();
    var epoch: usize = 1;
    while (epoch <= epochs) : (epoch += 1) {
        var loss: f64 = 0.0;
        for (dataset) |s| loss += net.trainStep(&s.x, &s.y);
        if (epoch % show_every == 0) {
            try stdout.print("epoch {d:5}  mse = {d:.6}\n", .{ epoch, loss / dataset.len });
        }
    }
}
EOF
    fill_placeholders "$f"
    add_file "$OUTPUT_DIR/zig/neural_network.zig"
}

gen_ocaml() {
    mkdir -p "$OUTPUT_DIR/ocaml"
    local f="$OUTPUT_DIR/ocaml/neural_network.ml"
    cat > "$f" <<'EOF'
(* neural_network.ml — idiomatic OCaml: record punning, Array combinators with
 * operator sections, a mutable activations cache, `let () =` entry point.
 * Build: ocamlopt neural_network.ml -o nn  && ./nn     (or: ocaml neural_network.ml)
 * Requires OCaml 4.07+.
 *
 * HOW IT WORKS
 * ------------
 * Network: n_in -> n_hidden (sigmoid) -> n_out (sigmoid), trained by SGD
 * on mean squared error.
 *
 * FORWARD   hidden.(j) = sigmoid(b1.(j) + sum_i x.(i) * w1.(i).(j))
 *           out.(k)    = sigmoid(b2.(k) + sum_j hidden.(j) * w2.(j).(k))
 *           sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)
 *
 * BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
 *           d_out.(k)    = (out.(k) - y.(k)) * out.(k) * (1 - out.(k))
 *           d_hidden.(j) = (sum_k d_out.(k) * w2.(j).(k)) * h.(j) * (1 - h.(j))
 *
 * UPDATE    every gradient = delta * activation feeding that edge:
 *           w2.(j).(k) -= lr * d_out.(k) * hidden.(j)
 *           w1.(i).(j) -= lr * d_hidden.(j) * x.(i)
 *
 * Replace the "toy dataset" block at the bottom with real data to train on it. *)

let sigmoid x = 1.0 /. (1.0 +. exp (-.x))

let gauss () =
  let rec uniform () =
    let u = Random.float 1.0 in
    if u = 0.0 then uniform () else u
  in
  sqrt (-2.0 *. log (uniform ())) *. cos (2.0 *. Float.pi *. Random.float 1.0)

let he_matrix rows cols =
  let scale = sqrt (2.0 /. float_of_int rows) in
  Array.init rows (fun _ -> Array.init cols (fun _ -> gauss () *. scale))

let dot_col v w col =
  (* v . w[:, col] over a row-major array-of-rows matrix *)
  Array.fold_left (+.) 0.0 (Array.mapi (fun i x -> x *. w.(i).(col)) v)

let dot_row v w row =
  Array.fold_left (+.) 0.0 (Array.map2 ( *. ) v w.(row))

type hyper = { n_in : int; n_hidden : int; n_out : int; lr : float }

type net = {
  hyper : hyper;
  w1 : float array array;
  b1 : float array;
  w2 : float array array;
  b2 : float array;
  mutable hidden : float array  (* cached activations for backprop *)
}

let init_net hyper seed =
  Random.init seed;
  { hyper;
    w1 = he_matrix hyper.n_in hyper.n_hidden;
    b1 = Array.make hyper.n_hidden 0.0;
    w2 = he_matrix hyper.n_hidden hyper.n_out;
    b2 = Array.make hyper.n_out 0.0;
    hidden = Array.make hyper.n_hidden 0.0 }

let forward net x =
  for j = 0 to net.hyper.n_hidden - 1 do
    net.hidden.(j) <- sigmoid (dot_col x net.w1 j +. net.b1.(j))
  done;
  Array.init net.hyper.n_out
    (fun k -> sigmoid (dot_row net.hidden net.w2 k +. net.b2.(k)))

let sq_err out y =
  Array.fold_left (+.) 0.0 (Array.map2 (fun o t -> let d = o -. t in d *. d) out y)

(* One SGD step; mutates the weight arrays in place — the standard OCaml
   style for numeric code (functional shell, imperative core). *)
let train_step net x y =
  let out = forward net x in
  let d_out =
    Array.map2 (fun o t -> (o -. t) *. o *. (1.0 -. o)) out y in
  let d_hidden =
    Array.mapi
      (fun j h -> dot_row d_out net.w2 j *. h *. (1.0 -. h))
      net.hidden in
  let lr = net.hyper.lr in
  for j = 0 to net.hyper.n_hidden - 1 do
    for k = 0 to net.hyper.n_out - 1 do
      net.w2.(j).(k) <- net.w2.(j).(k) -. lr *. d_out.(k) *. net.hidden.(j)
    done
  done;
  Array.iteri (fun k d -> net.b2.(k) <- net.b2.(k) -. lr *. d) d_out;
  for i = 0 to net.hyper.n_in - 1 do
    for j = 0 to net.hyper.n_hidden - 1 do
      net.w1.(i).(j) <- net.w1.(i).(j) -. lr *. d_hidden.(j) *. x.(i)
    done
  done;
  Array.iteri (fun j d -> net.b1.(j) <- net.b1.(j) -. lr *. d) d_hidden;
  sq_err out y

let () =
  let hyper =
    { n_in = __INPUT__; n_hidden = __HIDDEN__; n_out = __OUTPUT__; lr = __LR__ } in
  let epochs = __EPOCHS__ in
  let net = init_net hyper 42 in

  Random.init 7;  (* toy dataset — replace with your own *)
  let dataset =
    Array.init 64 (fun _ ->
      (Array.init hyper.n_in (fun _ -> Random.float 1.0),
       Array.init hyper.n_out (fun _ -> Random.float 1.0))) in

  let show_every = max (epochs / 10) 1 in
  for epoch = 1 to epochs do
    let loss =
      Array.fold_left (fun acc (x, y) -> acc +. train_step net x y) 0.0 dataset in
    if epoch mod show_every = 0 then
      Printf.printf "epoch %5d  mse = %.6f\n" epoch
        (loss /. float_of_int (Array.length dataset))
  done
EOF
    fill_placeholders "$f"
    add_file "$OUTPUT_DIR/ocaml/neural_network.ml"
}

gen_elixir() {
    mkdir -p "$OUTPUT_DIR/elixir"
    local f="$OUTPUT_DIR/elixir/neural_network.exs"
    cat > "$f" <<'EOF'
# neural_network.exs — idiomatic Elixir: immutable struct, pure functions
# returning {loss, net}, Enum.zip_with pipelines, comprehensions, :rand PRNG.
# Run: elixir neural_network.exs     (Elixir 1.12+, OTP 19+)
#
# HOW IT WORKS
# ------------
# Network: n_in -> n_hidden (sigmoid) -> n_out (sigmoid), trained by SGD on MSE.
#
# FORWARD   hidden[j] = sigmoid(b1[j] + dot(x, column j of w1))
#           out[k]    = sigmoid(b2[k] + dot(hidden, column k of w2))
#           sigmoid(z) = 1 / (1 + :math.exp(-z))  maps any value into (0,1)
#
# BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
#           d_out[k]    = (out[k] - y[k]) * out[k] * (1 - out[k])
#           d_hidden[j] = (sum_k d_out[k] * w2[j][k]) * hidden[j] * (1 - hidden[j])
#
# UPDATE    every gradient = delta * activation feeding that edge:
#           w2[j][k] -= lr * d_out[k] * hidden[j]    b2[k] -= lr * d_out[k]
#           w1[i][j] -= lr * d_hidden[j] * x[i]      b1[j] -= lr * d_hidden[j]
#
# Everything is immutable: train_step returns {sq_err, new_net}, and the
# demo threads the network through epochs with Enum.reduce/map_reduce.
# Replace the "toy dataset" block at the bottom with real data to train on it.

defmodule NeuralNetwork do
  @moduledoc "One-hidden-layer MLP with sigmoid activations, trained by SGD."

  defstruct [:lr, :w1, :b1, :w2, :b2]

  def new(n_in, n_hidden, n_out, lr, seed \\ 42) do
    :rand.seed(:exsss, seed)

    %__MODULE__{
      lr: lr,
      w1: he_matrix(n_in, n_hidden),   # He-style init
      b1: List.duplicate(0.0, n_hidden),
      w2: he_matrix(n_hidden, n_out),
      b2: List.duplicate(0.0, n_out)
    }
  end

  defp he_matrix(rows, cols) do
    scale = :math.sqrt(2 / rows)

    for _ <- 1..rows do
      for _ <- 1..cols, do: :rand.normal(0.0, 1.0) * scale
    end
  end

  defp sigmoid(x), do: 1 / (1 + :math.exp(-x))

  defp dot(a, b), do: Enum.zip_with(a, b, &*/2) |> Enum.sum()

  # List.zip pairs corresponding rows — the classic Elixir transpose trick.
  defp transpose(rows), do: rows |> List.zip() |> Enum.map(&Tuple.to_list/1)

  @doc "Returns {hidden, output} activations for one sample."
  def forward(%__MODULE__{w1: w1, b1: b1, w2: w2, b2: b2}, x) do
    hidden =
      b1
      |> Enum.zip(transpose(w1))
      |> Enum.map(fn {b, col} -> sigmoid(b + dot(x, col)) end)

    out =
      b2
      |> Enum.zip(transpose(w2))
      |> Enum.map(fn {b, col} -> sigmoid(b + dot(hidden, col)) end)

    {hidden, out}
  end

  @doc "One SGD step; returns {squared_error, updated_network}."
  def train_step(%__MODULE__{lr: lr} = net, x, y) do
    {hidden, out} = forward(net, x)

    # Output delta: error times sigmoid'(out).
    d_out = Enum.zip_with(out, y, fn o, t -> (o - t) * o * (1 - o) end)

    # Hidden delta: backpropagated error times sigmoid'(hidden).
    d_hidden =
      hidden
      |> Enum.zip(net.w2)
      |> Enum.map(fn {h, row} -> dot(d_out, row) * h * (1 - h) end)

    # Gradient descent: weight -= lr * delta * activation on that edge.
    w2 =
      net.w2
      |> Enum.zip(hidden)
      |> Enum.map(fn {row, h} ->
        Enum.zip_with(row, d_out, fn w, d -> w - lr * d * h end)
      end)

    b2 = Enum.zip_with(net.b2, d_out, fn b, d -> b - lr * d end)

    w1 =
      net.w1
      |> Enum.zip(x)
      |> Enum.map(fn {row, xi} ->
        Enum.zip_with(row, d_hidden, fn w, d -> w - lr * d * xi end)
      end)

    b1 = Enum.zip_with(net.b1, d_hidden, fn b, d -> b - lr * d end)

    sq_err =
      Enum.zip_with(out, y, fn o, t ->
        d = o - t
        d * d
      end)
      |> Enum.sum()

    {sq_err, %{net | w1: w1, b1: b1, w2: w2, b2: b2}}
  end
end

# ---- demo (replace with your own data) ----------------------------------
n_in = __INPUT__
n_hidden = __HIDDEN__
n_out = __OUTPUT__
lr = __LR__
epochs = __EPOCHS__

:rand.seed(:exsss, 7)

dataset =
  for _ <- 1..64 do
    {for _ <- 1..n_in, do: :rand.uniform(),
     for _ <- 1..n_out, do: :rand.uniform()}
  end

net = NeuralNetwork.new(n_in, n_hidden, n_out, lr, 42)
show_every = max(div(epochs, 10), 1)

# Enum.map_reduce threads the network through the dataset — the idiomatic
# way to fold a stateful accumulator over a collection.
_final_net =
  Enum.reduce(1..epochs, net, fn epoch, net ->
    {losses, net} =
      Enum.map_reduce(dataset, net, fn {x, y}, acc ->
        NeuralNetwork.train_step(acc, x, y)
      end)

    if rem(epoch, show_every) == 0 do
      mse = Enum.sum(losses) / 64

      IO.puts(
        "epoch #{String.pad_leading(Integer.to_string(epoch), 5)}  " <>
          "mse = #{:erlang.float_to_binary(mse, decimals: 6)}"
      )
    end

    net
  end)
EOF
    fill_placeholders "$f"
    add_file "$OUTPUT_DIR/elixir/neural_network.exs"
}

gen_groovy() {
    mkdir -p "$OUTPUT_DIR/groovy"
    local f="$OUTPUT_DIR/groovy/neural_network.groovy"
    cat > "$f" <<'EOF'
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
def hp = new HyperParams(nIn: __INPUT__, nHidden: __HIDDEN__,
                         nOut: __OUTPUT__, lr: __LR__)   // @Canonical map constructor
int epochs = __EPOCHS__
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
EOF
    fill_placeholders "$f"
    add_file "$OUTPUT_DIR/groovy/neural_network.groovy"
}

gen_objectivec() {
    mkdir -p "$OUTPUT_DIR/objectivec"
    local f="$OUTPUT_DIR/objectivec/main.m"
    cat > "$f" <<'EOF'
// main.m — idiomatic Objective-C: ARC, readonly properties, instancetype
// initializer pattern, C-array ivars for numeric data (the standard ObjC idiom
// for math), @autoreleasepool, NSLog, dealloc releasing C memory.
// Build (macOS, clang):  clang -fobjc-arc -framework Foundation main.m -o nn && ./nn
// Build (Linux):         install GNUstep, then compile with gnustep-config flags.
//
// HOW IT WORKS
// ------------
// Network: nIn -> nHidden (sigmoid) -> nOut (sigmoid), trained by SGD on MSE.
//
// FORWARD   hidden[j] = Sigmoid(b1[j] + sum_i x[i] * w1[i*nHid + j])
//           out[k]    = Sigmoid(b2[k] + sum_j hidden[j] * w2[j*nOut + k])
//           Sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)
//
// BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
//           dOut[k]    = (out[k] - y[k]) * out[k] * (1 - out[k])
//           dHidden[j] = (sum_k dOut[k] * w2[j*nOut+k]) * hidden[j] * (1 - hidden[j])
//
// UPDATE    every gradient = delta * activation feeding that edge:
//           w2[j*nOut+k] -= lr * dOut[k] * hidden[j]
//           w1[i*nHid+j] -= lr * dHidden[j] * x[i]
//
// Replace the "toy dataset" block in main() with real data to train on it.

#import <Foundation/Foundation.h>
#import <math.h>
#import <stdlib.h>

static double Sigmoid(double x) { return 1.0 / (1.0 + exp(-x)); }

static double Gauss(void) {
    double u = drand48();
    while (u == 0.0) u = drand48();
    return sqrt(-2.0 * log(u)) * cos(2.0 * M_PI * drand48());
}

@interface HyperParams : NSObject
@property (nonatomic, readonly) NSUInteger nIn, nHidden, nOut;
@property (nonatomic, readonly) double learningRate;
- (instancetype)initWithNIn:(NSUInteger)nIn
                   nHidden:(NSUInteger)nHidden
                      nOut:(NSUInteger)nOut
              learningRate:(double)lr;
@end

@implementation HyperParams
- (instancetype)initWithNIn:(NSUInteger)nIn
                   nHidden:(NSUInteger)nHidden
                      nOut:(NSUInteger)nOut
              learningRate:(double)lr {
    if (self = [super init]) {
        _nIn = nIn;
        _nHidden = nHidden;
        _nOut = nOut;
        _learningRate = lr;
    }
    return self;
}
@end

@interface NeuralNetwork : NSObject
@property (nonatomic, readonly) HyperParams *hp;
- (instancetype)initWithHyperParams:(HyperParams *)hp seed:(unsigned long)seed;
- (void)forwardWithInput:(const double *)x output:(double *)out;
- (double)trainStepWithInput:(const double *)x target:(const double *)y;
@end

@implementation NeuralNetwork {
    double *_w1, *_w2, *_b1, *_b2, *_hidden;  /* row-major C storage */
}

- (instancetype)initWithHyperParams:(HyperParams *)hp seed:(unsigned long)seed {
    if (self = [super init]) {
        _hp = hp;
        srand48(seed);
        NSUInteger ni = hp.nIn, nh = hp.nHidden, no = hp.nOut;
        _w1 = malloc(sizeof(double) * ni * nh);
        _w2 = malloc(sizeof(double) * nh * no);
        _b1 = calloc(nh, sizeof(double));
        _b2 = calloc(no, sizeof(double));
        _hidden = calloc(nh, sizeof(double));
        double s1 = sqrt(2.0 / (double)ni), s2 = sqrt(2.0 / (double)nh);
        for (NSUInteger i = 0; i < ni * nh; i++) _w1[i] = Gauss() * s1;  // He init
        for (NSUInteger i = 0; i < nh * no; i++) _w2[i] = Gauss() * s2;
    }
    return self;
}

/* Freeing C resources in dealloc is the canonical ARC pattern. */
- (void)dealloc {
    free(_w1); free(_w2); free(_b1); free(_b2); free(_hidden);
}

- (void)forwardWithInput:(const double *)x output:(double *)out {
    NSUInteger ni = self.hp.nIn, nh = self.hp.nHidden, no = self.hp.nOut;
    for (NSUInteger j = 0; j < nh; j++) {
        double z = _b1[j];
        for (NSUInteger i = 0; i < ni; i++) z += x[i] * _w1[i * nh + j];
        _hidden[j] = Sigmoid(z);
    }
    for (NSUInteger k = 0; k < no; k++) {
        double z = _b2[k];
        for (NSUInteger j = 0; j < nh; j++) z += _hidden[j] * _w2[j * no + k];
        out[k] = Sigmoid(z);
    }
}

- (double)trainStepWithInput:(const double *)x target:(const double *)y {
    NSUInteger ni = self.hp.nIn, nh = self.hp.nHidden, no = self.hp.nOut;
    double out[no], dOut[no], dHidden[nh];
    double sqErr = 0.0, lr = self.hp.learningRate;

    [self forwardWithInput:x output:out];
    for (NSUInteger k = 0; k < no; k++) {
        double d = out[k] - y[k];
        dOut[k] = d * out[k] * (1.0 - out[k]);       /* error * sigmoid'(out) */
        sqErr += d * d;
    }
    for (NSUInteger j = 0; j < nh; j++) {
        double back = 0.0;
        for (NSUInteger k = 0; k < no; k++) back += dOut[k] * _w2[j * no + k];
        dHidden[j] = back * _hidden[j] * (1.0 - _hidden[j]);
    }
    for (NSUInteger j = 0; j < nh; j++)
        for (NSUInteger k = 0; k < no; k++)
            _w2[j * no + k] -= lr * dOut[k] * _hidden[j];
    for (NSUInteger k = 0; k < no; k++) _b2[k] -= lr * dOut[k];
    for (NSUInteger i = 0; i < ni; i++)
        for (NSUInteger j = 0; j < nh; j++)
            _w1[i * nh + j] -= lr * dHidden[j] * x[i];
    for (NSUInteger j = 0; j < nh; j++) _b1[j] -= lr * dHidden[j];
    return sqErr;
}

@end

int main(void) {
    @autoreleasepool {
        HyperParams *hp =
            [[HyperParams alloc] initWithNIn:__INPUT__
                                    nHidden:__HIDDEN__
                                       nOut:__OUTPUT__
                               learningRate:__LR__];
        NeuralNetwork *net = [[NeuralNetwork alloc] initWithHyperParams:hp seed:42];

        srand48(7);  /* toy dataset — replace with your own */
        const NSUInteger samples = 64;
        double **x = malloc(sizeof(double *) * samples);
        double **y = malloc(sizeof(double *) * samples);
        for (NSUInteger s = 0; s < samples; s++) {
            x[s] = malloc(sizeof(double) * hp.nIn);
            y[s] = malloc(sizeof(double) * hp.nOut);
            for (NSUInteger i = 0; i < hp.nIn; i++) x[s][i] = drand48();
            for (NSUInteger k = 0; k < hp.nOut; k++) y[s][k] = drand48();
        }

        const int epochs = __EPOCHS__;
        const int showEvery = epochs / 10 > 0 ? epochs / 10 : 1;
        for (int epoch = 1; epoch <= epochs; epoch++) {
            double loss = 0.0;
            for (NSUInteger s = 0; s < samples; s++)
                loss += [net trainStepWithInput:x[s] target:y[s]];
            if (epoch % showEvery == 0)
                NSLog(@"epoch %5d  mse = %.6f", epoch, loss / (double)samples);
        }

        for (NSUInteger s = 0; s < samples; s++) { free(x[s]); free(y[s]); }
        free(x); free(y);
    }
    return 0;
}
EOF
    fill_placeholders "$f"
    add_file "$OUTPUT_DIR/objectivec/main.m"
}

gen_fortran() {
    mkdir -p "$OUTPUT_DIR/fortran"
    local f="$OUTPUT_DIR/fortran/neural_network.f90"
    cat > "$f" <<'EOF'
! neural_network.f90 — idiomatic modern Fortran: a module with a derived type
! and type-bound procedures, whole-array operations (matmul / elementwise),
! elemental functions, implicit none everywhere.
! Build: gfortran -O2 -std=f2018 neural_network.f90 -o nn && ./nn  (gfortran 9+)
!
! HOW IT WORKS
! ------------
! Network: n_in -> n_hidden (sigmoid) -> n_out (sigmoid), trained by SGD on MSE.
!
! FORWARD   hidden = sigmoid(matmul(x, w1) + b1)     (whole-array operations)
!           out    = sigmoid(matmul(hidden, w2) + b2)
!           sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)
!
! BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
!           d_out    = (out - y) * out * (1 - out)
!           d_hidden = matmul(w2, d_out) * hidden * (1 - hidden)
!
! UPDATE    rank-1 outer products via reshape + matmul:
!           w2 -= lr * hidden (outer) d_out     b2 -= lr * d_out
!           w1 -= lr * x (outer) d_hidden       b1 -= lr * d_hidden
!
! Replace the "toy dataset" block in the program with real data to train on it.

module neural_network_mod
   use, intrinsic :: iso_fortran_env, only: real64
   implicit none
   private
   public :: mlp, new_mlp

   type :: mlp
      real(real64) :: lr
      real(real64), allocatable :: w1(:, :), b1(:), w2(:, :), b2(:), hidden(:)
   contains
      procedure :: forward => mlp_forward
      procedure :: train_step => mlp_train_step
   end type mlp

contains

   elemental real(real64) function sigmoid(x) result(s)
      real(real64), intent(in) :: x
      s = 1.0_real64/(1.0_real64 + exp(-x))
   end function sigmoid

   function gauss() result(g)
      real(real64) :: u, v, g
      do
         call random_number(u)
         if (u > tiny(1.0_real64)) exit
      end do
      call random_number(v)
      g = sqrt(-2.0_real64*log(u))*cos(2.0_real64*acos(-1.0_real64)*v)
   end function gauss

   function new_mlp(n_in, n_hidden, n_out, lr) result(net)
      integer, intent(in) :: n_in, n_hidden, n_out
      real(real64), intent(in) :: lr
      type(mlp) :: net
      real(real64) :: s1, s2
      integer :: i, j

      net%lr = lr
      allocate (net%w1(n_in, n_hidden), net%b1(n_hidden))
      allocate (net%w2(n_hidden, n_out), net%b2(n_out))
      allocate (net%hidden(n_hidden))
      net%b1 = 0.0_real64;  net%b2 = 0.0_real64
      s1 = sqrt(2.0_real64/n_in);  s2 = sqrt(2.0_real64/n_hidden)
      do j = 1, n_hidden
         do i = 1, n_in
            net%w1(i, j) = gauss()*s1
         end do
      end do
      do j = 1, n_out
         do i = 1, n_hidden
            net%w2(i, j) = gauss()*s2
         end do
      end do
   end function new_mlp

   ! Whole-array operations: matmul + elemental sigmoid do the loops for us.
   function mlp_forward(self, x) result(out)
      class(mlp), intent(inout) :: self
      real(real64), intent(in) :: x(:)
      real(real64) :: out(size(self%b2))

      self%hidden = sigmoid(matmul(x, self%w1) + self%b1)
      out = sigmoid(matmul(self%hidden, self%w2) + self%b2)
   end function mlp_forward

   function mlp_train_step(self, x, y) result(sq_err)
      class(mlp), intent(inout) :: self
      real(real64), intent(in) :: x(:), y(:)
      real(real64) :: out(size(y)), d_out(size(y)), d_hidden(size(self%b1))
      real(real64) :: sq_err

      out = self%forward(x)
      sq_err = sum((out - y)**2)                      ! elementwise array math

      d_out = (out - y)*out*(1.0_real64 - out)
      d_hidden = matmul(self%w2, d_out)*self%hidden*(1.0_real64 - self%hidden)

      ! Rank-1 weight updates expressed as outer products via matmul/reshape.
      self%w2 = self%w2 - self%lr*matmul( &
         reshape(self%hidden, [size(self%hidden), 1]), &
         reshape(d_out, [1, size(d_out)]))
      self%b2 = self%b2 - self%lr*d_out
      self%w1 = self%w1 - self%lr*matmul( &
         reshape(x, [size(x), 1]), &
         reshape(d_hidden, [1, size(d_hidden)]))
      self%b1 = self%b1 - self%lr*d_hidden
   end function mlp_train_step

end module neural_network_mod

program demo
   use, intrinsic :: iso_fortran_env, only: real64
   use neural_network_mod, only: mlp, new_mlp
   implicit none

   integer, parameter :: n_in = __INPUT__, n_hidden = __HIDDEN__, n_out = __OUTPUT__
   integer, parameter :: n_samples = 64, epochs = __EPOCHS__
   real(real64), parameter :: lr = __LR__
   integer, parameter :: show_every = max(epochs/10, 1)

   type(mlp) :: net
   real(real64) :: x(n_samples, n_in), y(n_samples, n_out)
   real(real64) :: loss, sample_x(n_in), sample_y(n_out)
   integer :: epoch, s

   call random_init(repeatable=.true., image_distinct=.false.)  ! F2018
   net = new_mlp(n_in, n_hidden, n_out, lr)

   ! Toy dataset — replace with your own.
   call random_number(x)
   call random_number(y)

   do epoch = 1, epochs
      loss = 0.0_real64
      do s = 1, n_samples
         sample_x = x(s, :);  sample_y = y(s, :)
         loss = loss + net%train_step(sample_x, sample_y)
      end do
      if (mod(epoch, show_every) == 0) &
         print '(a, i5, a, f0.6)', 'epoch', epoch, '  mse = ', loss/n_samples
   end do
end program demo
EOF
    fill_placeholders "$f"
    add_file "$OUTPUT_DIR/fortran/neural_network.f90"
}

gen_powershell() {
    mkdir -p "$OUTPUT_DIR/powershell"
    local f="$OUTPUT_DIR/powershell/neural_network.ps1"
    cat > "$f" <<'EOF'
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
    NIn     = __INPUT__
    NHidden = __HIDDEN__
    NOut    = __OUTPUT__
    Lr      = __LR__
}
 $epochs = __EPOCHS__

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
EOF
    fill_placeholders "$f"
    add_file "$OUTPUT_DIR/powershell/neural_network.ps1"
}

# ---------------------------------------------------------------- summary
print_summary() {
    echo
    printf '%s%s%s\n' "$C_GRN" "==================================================" "$C_OFF"
    echo " Done! ${#CREATED[@]} files generated in $OUTPUT_DIR"
    printf '%s%s%s\n' "$C_GRN" "==================================================" "$C_OFF"
    local f
    for f in "${CREATED[@]}"; do
        echo "  - $f"
    done
    echo
    echo "Next steps:"
    echo "  1. Each generated file lists its run/build command in the header comment"
    echo "  2. Every file has a HOW IT WORKS block explaining the network math"
    echo "  3. Replace the toy random dataset in each demo with real data"
}

# ---------------------------------------------------------------- main
main() {
    parse_args "$@"

    if [[ ${#SELECTED[@]} -eq 0 ]]; then
        if [[ -t 0 ]]; then
            interactive_menu
        else
            die "No languages specified. e.g. ./generate_nn.sh python cpp"
        fi
    fi

    resolve_langs

    [[ -f "$OUTPUT_DIR/README.md" ]] && \
        warn "stale $OUTPUT_DIR/README.md from an earlier run — remove it manually if unwanted"

    echo
    info "Generating neural network (in=${INPUT_SIZE}, hidden=${HIDDEN_SIZE}, out=${OUTPUT_SIZE}, lr=${LEARNING_RATE}, epochs=${EPOCHS})"
    info "Languages: ${LANGS[*]}"
    echo

    local lang
    for lang in "${LANGS[@]}"; do
        case "$lang" in
            python)     gen_python ;;
            cpp)        gen_cpp ;;
            c)          gen_c ;;
            java)       gen_java ;;
            javascript) gen_javascript ;;
            typescript) gen_typescript ;;
            go)         gen_go ;;
            rust)       gen_rust ;;
            ruby)       gen_ruby ;;
            kotlin)     gen_kotlin ;;
            swift)      gen_swift ;;
            csharp)     gen_csharp ;;
            dart)       gen_dart ;;
            php)        gen_php ;;
            perl)       gen_perl ;;
            lua)        gen_lua ;;
            haskell)    gen_haskell ;;
            r)          gen_r ;;
            julia)      gen_julia ;;
            scala)      gen_scala ;;
            fsharp)     gen_fsharp ;;
            nim)        gen_nim ;;
            zig)        gen_zig ;;
            ocaml)      gen_ocaml ;;
            elixir)     gen_elixir ;;
            groovy)     gen_groovy ;;
            objectivec) gen_objectivec ;;
            fortran)    gen_fortran ;;
            powershell) gen_powershell ;;
        esac
    done

    print_summary
}

main "$@"