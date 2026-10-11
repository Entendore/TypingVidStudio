module BuildingMonads where

import Control.Monad.State

{-
  ============================================================================
  🟢 PART 2: BUILDING MONADS & THE MONAD LAWS
  ============================================================================
  Every Monad must be a Functor and an Applicative.
  LAW 1 (Left Identity):  return x >>= f  ==  f x
  LAW 2 (Right Identity): m >>= return    ==  m
  LAW 3 (Associativity):  (m >>= f) >>= g ==  m >>= (\x -> f x >>= g)
-}

-- 1. CUSTOM LOGGER MONAD
data Logger a = Logger { getLogs :: [String], getValue :: a } deriving (Show)

instance Functor Logger where
  fmap f (Logger logs val) = Logger logs (f val)

instance Applicative Logger where
  pure x = Logger [] x
  Logger l1 f <*> Logger l2 v = Logger (l1 ++ l2) (f v)

instance Monad Logger where
  return = pure
  Logger oldLogs val >>= k = 
    let Logger newLogs newVal = k val
    in Logger (oldLogs ++ newLogs) newVal

logMsg :: String -> Logger ()
logMsg msg = Logger [msg] ()

customLogger :: Logger Int
customLogger = do
  logMsg "Start"
  let x = 10
  logMsg $ "x is " ++ show x
  return (x * 2)

-- 2. STATE MONAD
type Counter = State Int

increment :: Counter Int
increment = do
  modify' (+ 1) -- modify' is the strict version (prevents space leaks!)
  get

main :: IO ()
main = do
  putStrLn "--- CUSTOM LOGGER ---"
  let result = customLogger
  putStrLn $ "Value: " ++ show (getValue result)
  putStrLn $ "Logs: " ++ show (getLogs result)
  
  putStrLn "\n--- STATE MONAD ---"
  let (finalVal, finalState) = runState (replicateM_ 3 increment >> get) 0
  putStrLn $ "Final State: " ++ show finalState
