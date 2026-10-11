module Production where

import Control.Monad.Reader (ReaderT, runReaderT, asks)
import Control.Monad.IO.Class (MonadIO, liftIO)
import Control.Monad.Reader.Class (MonadReader)

{-
  ============================================================================
  🟢 PART 4: PRODUCTION HASKELL (The ReaderT Design Pattern)
  ============================================================================
  DON'T stack 5 transformers. DO use `ReaderT Env IO`.
  It provides Dependency Injection and keeps IO at the bottom for exceptions.
-}

data AppEnv = AppEnv { envDbConn :: String, envApiKey :: String }
type AppM a = ReaderT AppEnv IO a

fetchData :: Int -> AppM String
fetchData userId = do
  conn <- asks envDbConn
  liftIO $ putStrLn $ "[DB] Querying via " ++ conn
  return $ "Data for user " ++ show userId

-- Decoupled using Typeclasses (Makes it testable!)
decoupledFetch :: (MonadReader env m, MonadIO m) => (env -> String) -> m String
decoupledFetch getConn = do
  conn <- asks getConn
  liftIO $ putStrLn $ "[Mock DB] Using " ++ conn
  return "Mock Data"

main :: IO ()
main = do
  let env = AppEnv "Postgres_Pool" "secret_key"
  
  putStrLn "--- READERT PATTERN ---"
  res1 <- runReaderT (fetchData 42) env
  putStrLn $ "Result: " ++ res1
  
  putStrLn "\n--- DECOUPLED LOGIC ---"
  res2 <- runReaderT (decoupledFetch envDbConn) env
  putStrLn $ "Result: " ++ res2
