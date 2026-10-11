(* neural_network.ml — idiomatic OCaml: record punning, Array combinators with
 * operator sections, a mutable activations cache, `let () =` entry point.
 * Build: ocamlopt neural_network.ml -o nn  && ./nn     (or: ocaml neural_network.ml)
 * Requires OCaml 4.07+.
 *
 * HOW IT WORKS
 * ------------
 * Network: n_in -> n_hidden (sigmoid) -> n_out (sigmoid), trained by SGD
 * on mean squared error.
 *
 * FORWARD   hidden.(j) = sigmoid(b1.(j) + sum_i x.(i) * w1.(i).(j))
 *           out.(k)    = sigmoid(b2.(k) + sum_j hidden.(j) * w2.(j).(k))
 *           sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)
 *
 * BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
 *           d_out.(k)    = (out.(k) - y.(k)) * out.(k) * (1 - out.(k))
 *           d_hidden.(j) = (sum_k d_out.(k) * w2.(j).(k)) * h.(j) * (1 - h.(j))
 *
 * UPDATE    every gradient = delta * activation feeding that edge:
 *           w2.(j).(k) -= lr * d_out.(k) * hidden.(j)
 *           w1.(i).(j) -= lr * d_hidden.(j) * x.(i)
 *
 * Replace the "toy dataset" block at the bottom with real data to train on it. *)

let sigmoid x = 1.0 /. (1.0 +. exp (-.x))

let gauss () =
  let rec uniform () =
    let u = Random.float 1.0 in
    if u = 0.0 then uniform () else u
  in
  sqrt (-2.0 *. log (uniform ())) *. cos (2.0 *. Float.pi *. Random.float 1.0)

let he_matrix rows cols =
  let scale = sqrt (2.0 /. float_of_int rows) in
  Array.init rows (fun _ -> Array.init cols (fun _ -> gauss () *. scale))

let dot_col v w col =
  (* v . w[:, col] over a row-major array-of-rows matrix *)
  Array.fold_left (+.) 0.0 (Array.mapi (fun i x -> x *. w.(i).(col)) v)

let dot_row v w row =
  Array.fold_left (+.) 0.0 (Array.map2 ( *. ) v w.(row))

type hyper = { n_in : int; n_hidden : int; n_out : int; lr : float }

type net = {
  hyper : hyper;
  w1 : float array array;
  b1 : float array;
  w2 : float array array;
  b2 : float array;
  mutable hidden : float array  (* cached activations for backprop *)
}

let init_net hyper seed =
  Random.init seed;
  { hyper;
    w1 = he_matrix hyper.n_in hyper.n_hidden;
    b1 = Array.make hyper.n_hidden 0.0;
    w2 = he_matrix hyper.n_hidden hyper.n_out;
    b2 = Array.make hyper.n_out 0.0;
    hidden = Array.make hyper.n_hidden 0.0 }

let forward net x =
  for j = 0 to net.hyper.n_hidden - 1 do
    net.hidden.(j) <- sigmoid (dot_col x net.w1 j +. net.b1.(j))
  done;
  Array.init net.hyper.n_out
    (fun k -> sigmoid (dot_row net.hidden net.w2 k +. net.b2.(k)))

let sq_err out y =
  Array.fold_left (+.) 0.0 (Array.map2 (fun o t -> let d = o -. t in d *. d) out y)

(* One SGD step; mutates the weight arrays in place — the standard OCaml
   style for numeric code (functional shell, imperative core). *)
let train_step net x y =
  let out = forward net x in
  let d_out =
    Array.map2 (fun o t -> (o -. t) *. o *. (1.0 -. o)) out y in
  let d_hidden =
    Array.mapi
      (fun j h -> dot_row d_out net.w2 j *. h *. (1.0 -. h))
      net.hidden in
  let lr = net.hyper.lr in
  for j = 0 to net.hyper.n_hidden - 1 do
    for k = 0 to net.hyper.n_out - 1 do
      net.w2.(j).(k) <- net.w2.(j).(k) -. lr *. d_out.(k) *. net.hidden.(j)
    done
  done;
  Array.iteri (fun k d -> net.b2.(k) <- net.b2.(k) -. lr *. d) d_out;
  for i = 0 to net.hyper.n_in - 1 do
    for j = 0 to net.hyper.n_hidden - 1 do
      net.w1.(i).(j) <- net.w1.(i).(j) -. lr *. d_hidden.(j) *. x.(i)
    done
  done;
  Array.iteri (fun j d -> net.b1.(j) <- net.b1.(j) -. lr *. d) d_hidden;
  sq_err out y

let () =
  let hyper =
    { n_in = 4; n_hidden = 8; n_out = 2; lr = 0.5 } in
  let epochs = 1000 in
  let net = init_net hyper 42 in

  Random.init 7;  (* toy dataset — replace with your own *)
  let dataset =
    Array.init 64 (fun _ ->
      (Array.init hyper.n_in (fun _ -> Random.float 1.0),
       Array.init hyper.n_out (fun _ -> Random.float 1.0))) in

  let show_every = max (epochs / 10) 1 in
  for epoch = 1 to epochs do
    let loss =
      Array.fold_left (fun acc (x, y) -> acc +. train_step net x y) 0.0 dataset in
    if epoch mod show_every = 0 then
      Printf.printf "epoch %5d  mse = %.6f\n" epoch
        (loss /. float_of_int (Array.length dataset))
  done
