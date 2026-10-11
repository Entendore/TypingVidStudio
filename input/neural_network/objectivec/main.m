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
            [[HyperParams alloc] initWithNIn:4
                                    nHidden:8
                                       nOut:2
                               learningRate:0.5];
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

        const int epochs = 1000;
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
