// neural_network.fsx — idiomatic F#: module of pure functions, records with
// functional updates ({ net with ... }), pipelines, Array combinators.
// Run: dotnet fsi neural_network.fsx        (.NET 6+ / F# 6+)
//
// HOW IT WORKS
// ------------
// Network: NIn -> NHidden (sigmoid) -> NOut (sigmoid), trained by SGD on MSE.
//
// FORWARD   hidden[j] = sigmoid(B1[j] + sum_i x[i] * W1[i,j])
//           out[k]    = sigmoid(B2[k] + sum_j hidden[j] * W2[j,k])
//           sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)
//
// BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
//           dOut[k]    = (out[k] - y[k]) * out[k] * (1 - out[k])
//           dHidden[j] = (sum_k dOut[k] * W2[j,k]) * hidden[j] * (1 - hidden[j])
//
// UPDATE    every gradient = delta * activation feeding that edge:
//           W2[j,k] -= lr * dOut[k] * hidden[j]     B2[k] -= lr * dOut[k]
//           W1[i,j] -= lr * dHidden[j] * x[i]       B1[j] -= lr * dHidden[j]
//
// Replace the "toy dataset" block at the bottom with real data to train on it.

module Neural

let sigmoid (z: float) : float = 1.0 / (1.0 + exp -z)

type Hyper = { NIn: int; NHidden: int; NOut: int; Lr: float }

type Net =
    { Hyper: Hyper
      W1: float[,]
      B1: float[]
      W2: float[,]
      B2: float[]
      mutable Hidden: float[] }   // cache for backprop; contents replaced per step

let private gauss (rng: System.Random) =
    let rec loop () =
        let u = rng.NextDouble()
        if u = 0.0 then loop () else u
    sqrt (-2.0 * log (loop ())) * cos (2.0 * System.Math.PI * rng.NextDouble())

let init (hyper: Hyper) (rng: System.Random) : Net =
    let he rows cols =
        let scale = sqrt (2.0 / float rows)
        Array2D.init rows cols (fun _ _ -> gauss rng * scale)
    { Hyper = hyper
      W1 = he hyper.NIn hyper.NHidden
      B1 = Array.zeroCreate hyper.NHidden
      W2 = he hyper.NHidden hyper.NOut
      B2 = Array.zeroCreate hyper.NOut
      Hidden = Array.zeroCreate hyper.NHidden }

let private dotCol v w col =
    Array.sumBy (fun i -> v[i] * w[i, col]) [| 0 .. Array2D.length1 w - 1 |]

let forward (net: Net) (x: float[]) : float[] * float[] =
    let hidden =
        Array.init net.Hyper.NHidden (fun j ->
            sigmoid (net.B1[j] + dotCol x net.W1 j))
    let out =
        Array.init net.Hyper.NOut (fun k ->
            sigmoid (net.B2[k] + dotCol hidden net.W2 k))
    net.Hidden <- hidden
    hidden, out

/// One SGD step; returns (squared error, updated net) — pure at the API level.
let step (net: Net) (x: float[]) (y: float[]) : float * Net =
    let hidden, out = forward net x

    let dOut = Array.map2 (fun o t -> (o - t) * o * (1.0 - o)) out y
    let dHid =
        Array.init net.Hyper.NHidden (fun j ->
            let back = Array.sumBy (fun k -> dOut[k] * net.W2[j, k]) [| 0 .. net.Hyper.NOut - 1 |]
            back * hidden[j] * (1.0 - hidden[j]))

    let lr = net.Hyper.Lr
    let w2' = Array2D.init net.Hyper.NHidden net.Hyper.NOut
                (fun j k -> net.W2[j, k] - lr * dOut[k] * hidden[j])
    let w1' = Array2D.init net.Hyper.NIn net.Hyper.NHidden
                (fun i j -> net.W1[i, j] - lr * dHid[j] * x[i])
    let b2' = Array.mapi2 (fun k b d -> b - lr * d) net.B2 dOut
    let b1' = Array.mapi2 (fun j b d -> b - lr * d) net.B1 dHid

    let sqErr =
        Array.map2 (fun o t -> let d = o - t in d * d) out y |> Array.sum
    sqErr, { net with W1 = w1'; B1 = b1'; W2 = w2'; B2 = b2' }

/// One epoch; returns (mean squared error, updated net) via a left fold.
let epoch (net: Net) (dataset: (float[] * float[])[]) : float * Net =
    dataset
    |> Array.fold (fun (total, n) (x, y) ->
            let err, n' = step n x y
            total + err, n') (0.0, net)
    |> fun (total, n) -> total / float (Array.length dataset), n

// ---- demo (replace with your own data) ------------------------------
open Neural

let hyper = { NIn = 4; NHidden = 8; NOut = 2; Lr = 0.5 }
let epochs = 1000

let net0 = init hyper (System.Random 42)

let data = System.Random 7
let dataset =
    Array.init 64 (fun _ ->
        Array.init hyper.NIn (fun _ -> data.NextDouble()),
        Array.init hyper.NOut (fun _ -> data.NextDouble()))

let showEvery = max (epochs / 10) 1

let rec run (net: Net) epoch =
    if epoch > epochs then net
    else
        let loss, net' = epoch net dataset
        if epoch % showEvery = 0 then
            printfn "epoch %5d  mse = %.6f" epoch loss
        run net' (epoch + 1)

let _finalNet = run net0 1
