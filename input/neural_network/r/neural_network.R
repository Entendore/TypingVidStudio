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
n_in <- 4
n_hidden <- 8
n_out <- 2

net <- new_neural_network(n_in, n_hidden, n_out, learning_rate = 0.5)
print(net)

X <- matrix(runif(64 * n_in), nrow = 64)
y <- matrix(runif(64 * n_out), nrow = 64)

net <- train(net, X, y, epochs = 1000)

print(round(predict(net, head(X, 5)), 3))
