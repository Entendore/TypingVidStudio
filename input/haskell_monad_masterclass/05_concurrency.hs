module Concurrency where

import Control.Concurrent (forkIO, threadDelay)
import Control.Concurrent.STM
import Control.Monad (when, replicateM_)

{-
  ============================================================================
  🟢 PART 5: CONCURRENCY & STM (Lock-Free Shared State)
  ============================================================================
  STM treats memory like a database. Use TVar, atomically, and retry.
  No locks, no deadlocks!
-}

withdraw :: TVar Double -> Double -> STM ()
withdraw acc amount = do
  bal <- readTVar acc
  when (bal < amount) retry -- 💡 MAGIC: Suspends until the TVar changes!
  writeTVar acc (bal - amount)

deposit :: TVar Double -> Double -> STM ()
deposit acc amount = modifyTVar' acc (+ amount)

main :: IO ()
main = do
  acc <- newTVarIO 50.0
  
  putStrLn "--- STM CONCURRENT TRANSFERS ---"
  
  -- Thread 1: Tries to withdraw $100. Will `retry` and block safely.
  _ <- forkIO $ do
    putStrLn "[Thread 1] Trying to withdraw $100..."
    atomically $ withdraw acc 100.0
    putStrLn "[Thread 1] Success! Withdrew $100."
    
  -- Thread 2: Waits a bit, then deposits $200.
  _ <- forkIO $ do
    threadDelay 1000000 -- 1 second
    putStrLn "[Thread 2] Depositing $200..."
    atomically $ deposit acc 200.0
    putStrLn "[Thread 2] Deposited!"
    
  threadDelay 2000000 -- Wait for threads to finish
  final <- readTVarIO acc
  putStrLn $ "Final Balance: $" ++ show final
