module Basics where

import Control.Monad (guard)

{-
  ============================================================================
  🟢 PART 1: THE BASICS (Maybe, List, IO, and Do Notation)
  ============================================================================
  Monads are design patterns for chaining operations while managing context.
  - Maybe: Handles missing values/failures.
  - List: Handles non-determinism (multiple results).
  - IO: Handles side effects (the real world).
-}

-- 1. MAYBE MONAD: Chaining operations that might fail
safeDiv :: Double -> Double -> Maybe Double
safeDiv _ 0 = Nothing
safeDiv x y = Just (x / y)

safeSqrt :: Double -> Maybe Double
safeSqrt x | x < 0     = Nothing
           | otherwise = Just (sqrt x)

-- Using `do` notation (Syntactic sugar for the >>= bind operator)
chainMaybe :: Double -> Double -> Maybe Double
chainMaybe a b = do
  divided <- safeDiv a b   -- If Nothing, the whole block short-circuits to Nothing
  rooted  <- safeSqrt divided
  return rooted            -- Wraps the final value back into Just

-- 2. LIST MONAD: Generating combinations
listCombinations :: [(Int, Int)]
listCombinations = do
  x <- [1..3]
  y <- [1..3]
  guard (x + y == 4) -- Filters out pairs that don't sum to 4
  return (x, y)

-- 3. IO MONAD: Interacting with the world
ioExample :: IO ()
ioExample = do
  putStrLn "What is your name?"
  name <- getLine  -- Extracts the String from the IO context
  putStrLn $ "Hello, " ++ name ++ "!"

main :: IO ()
main = do
  putStrLn "--- MAYBE ---"
  print $ chainMaybe 10 2  -- Just 2.23...
  print $ chainMaybe 10 0  -- Nothing
  
  putStrLn "\n--- LIST ---"
  print $ listCombinations -- [(1,3),(2,2),(3,1)]
  
  putStrLn "\n--- IO ---"
  ioExample
