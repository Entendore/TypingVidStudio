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
    const size_t n_in = 4, n_hid = 8, n_out = 2;
    const double lr = 0.5;
    const int epochs = 1000;

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
