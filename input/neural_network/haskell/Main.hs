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
  let nI     = 4
      nH     = 8
      nO     = 2
      rate   = 0.5
      epochs = 1000 :: Int
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
