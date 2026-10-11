module DosAndDonts where

import Control.Monad (forM_, when)
import Control.Monad.IO.Class (liftIO)
import Data.IORef

{-
  ============================================================================
  🟢 PART 6: DOS AND DON'TS OF HASKELL MONADS
  ============================================================================
  Crucial best practices and anti-patterns for production Haskell.
-}

-- ✅ DO: Use `pure` instead of `return` when Applicative is enough.
-- `pure` is more general and doesn't imply monadic sequencing.
doUsePure :: Maybe Int
doUsePure = pure 42 

-- ✅ DO: Use `traverse_` or `mapM_` for side-effectful loops.
-- It's clean, idiomatic, and safely discards the [()] result.
doUseTraverse :: IO ()
doUseTraverse = forM_ [1..3] $ \i -> 
  putStrLn $ "Processing item: " ++ show i

-- ❌ DON'T: Use `StateT s IO`. 
-- WHY? StateT is lazy by default. Threading large state through IO causes 
-- massive space leaks (thunks building up in memory).
-- ✅ DO: Use `IORef` for simple state, or `STM` (TVar) for concurrent state.
dontUseStateTOverIO :: IORef Int -> IO ()
dontUseStateTOverIO ref = do
  modifyIORef' ref (+ 1) -- Note the prime (') for STRICT modification!
  val <- readIORef ref
  putStrLn $ "Current strict value: " ++ show val

-- ❌ DON'T: Use `unsafePerformIO` to cheat and run IO in pure code.
-- WHY? It breaks referential transparency. The compiler might reorder or 
-- duplicate your IO actions, leading to unpredictable, nightmarish bugs.
-- ✅ DO: Keep IO in the IO monad. 

-- ❌ DON'T: Fall into "Transformer Hell".
-- DON'T stack 4+ transformers (e.g., StateT (ExceptT (ReaderT (WriterT IO)))).
-- WHY? Terrible compile times, type inference failures, and performance hits.
-- ✅ DO: Use the `ReaderT Env IO` pattern (see File 04).

-- ✅ DO: Use strict fields (!) in State/STM to prevent space leaks.
data StrictState = StrictState
  { ssCounter :: !Int  -- The '!' forces strict evaluation
  , ssAccum   :: !Double
  } deriving (Show)

main :: IO ()
main = do
  putStrLn "=== DOS AND DON'TS OF HASKELL MONADS ==="
  print doUsePure
  doUseTraverse
  
  ref <- newIORef 0
  dontUseStateTOverIO ref
  
  putStrLn "\n✅ Golden Rules:"
  putStrLn "   1. Keep business logic pure (Maybe/Either/State)."
  putStrLn "   2. Use ReaderT Env IO for application architecture."
  putStrLn "   3. Use STM for concurrent shared state."
  putStrLn "   4. Always use strict variants (modifyIORef', modifyTVar')!"
