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

constexpr double kLearningRate = 0.5;
constexpr int kEpochs = 1000;

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
    constexpr std::size_t kIn = 4, kHid = 8, kOut = 2;

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
