module Transformers where

import Control.Monad.Trans.Except (ExceptT, runExceptT, throwE)
import Control.Monad.Trans.State (State, runState, get, put)
import Control.Monad.Trans.Class (lift)
import Data.Map.Strict (Map)
import qualified Data.Map.Strict as Map

{-
  ============================================================================
  🟢 PART 3: MONAD TRANSFORMERS (Combining Monads)
  ============================================================================
  Transformers stack monads. ORDER MATTERS!
  ExceptT over State = Rollback on failure (Transaction).
  StateT over Except = Partial commit on failure.
-}

type Balances = Map String Double
type BankM a = ExceptT String (State Balances) a

transfer :: String -> String -> Double -> BankM ()
transfer from to amount = do
  balances <- lift get -- 'lift' brings inner monad (State) actions into ExceptT
  let fromBal = Map.findWithDefault 0.0 from balances
  let toBal   = Map.findWithDefault 0.0 to balances
  
  if fromBal < amount
    then throwE "Insufficient funds!"
    else do
      let newBals = Map.insert from (fromBal - amount) $ Map.insert to (toBal + amount) balances
      lift $ put newBals

main :: IO ()
main = do
  let initial = Map.fromList [("Alice", 100.0), ("Bob", 50.0)]
      pipeline = do
        transfer "Alice" "Bob" 30.0  -- Success
        transfer "Bob" "Alice" 999.0 -- Fails!
        
      -- Unpack the transformer onion: ExceptT first, then State
      (result, finalBals) = runState (runExceptT pipeline) initial
      
  putStrLn "--- BANK TRANSACTION ---"
  case result of
    Left err -> putStrLn $ "❌ Failed: " ++ err ++ "\nState rolled back: " ++ show finalBals
    Right _  -> putStrLn $ "✅ Success: " ++ show finalBals
