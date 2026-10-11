! neural_network.f90 — idiomatic modern Fortran: a module with a derived type
! and type-bound procedures, whole-array operations (matmul / elementwise),
! elemental functions, implicit none everywhere.
! Build: gfortran -O2 -std=f2018 neural_network.f90 -o nn && ./nn  (gfortran 9+)
!
! HOW IT WORKS
! ------------
! Network: n_in -> n_hidden (sigmoid) -> n_out (sigmoid), trained by SGD on MSE.
!
! FORWARD   hidden = sigmoid(matmul(x, w1) + b1)     (whole-array operations)
!           out    = sigmoid(matmul(hidden, w2) + b2)
!           sigmoid(z) = 1 / (1 + exp(-z))  maps any value into (0,1)
!
! BACKPROP  (chain rule; sigmoid derivative at activated value a is a*(1-a)):
!           d_out    = (out - y) * out * (1 - out)
!           d_hidden = matmul(w2, d_out) * hidden * (1 - hidden)
!
! UPDATE    rank-1 outer products via reshape + matmul:
!           w2 -= lr * hidden (outer) d_out     b2 -= lr * d_out
!           w1 -= lr * x (outer) d_hidden       b1 -= lr * d_hidden
!
! Replace the "toy dataset" block in the program with real data to train on it.

module neural_network_mod
   use, intrinsic :: iso_fortran_env, only: real64
   implicit none
   private
   public :: mlp, new_mlp

   type :: mlp
      real(real64) :: lr
      real(real64), allocatable :: w1(:, :), b1(:), w2(:, :), b2(:), hidden(:)
   contains
      procedure :: forward => mlp_forward
      procedure :: train_step => mlp_train_step
   end type mlp

contains

   elemental real(real64) function sigmoid(x) result(s)
      real(real64), intent(in) :: x
      s = 1.0_real64/(1.0_real64 + exp(-x))
   end function sigmoid

   function gauss() result(g)
      real(real64) :: u, v, g
      do
         call random_number(u)
         if (u > tiny(1.0_real64)) exit
      end do
      call random_number(v)
      g = sqrt(-2.0_real64*log(u))*cos(2.0_real64*acos(-1.0_real64)*v)
   end function gauss

   function new_mlp(n_in, n_hidden, n_out, lr) result(net)
      integer, intent(in) :: n_in, n_hidden, n_out
      real(real64), intent(in) :: lr
      type(mlp) :: net
      real(real64) :: s1, s2
      integer :: i, j

      net%lr = lr
      allocate (net%w1(n_in, n_hidden), net%b1(n_hidden))
      allocate (net%w2(n_hidden, n_out), net%b2(n_out))
      allocate (net%hidden(n_hidden))
      net%b1 = 0.0_real64;  net%b2 = 0.0_real64
      s1 = sqrt(2.0_real64/n_in);  s2 = sqrt(2.0_real64/n_hidden)
      do j = 1, n_hidden
         do i = 1, n_in
            net%w1(i, j) = gauss()*s1
         end do
      end do
      do j = 1, n_out
         do i = 1, n_hidden
            net%w2(i, j) = gauss()*s2
         end do
      end do
   end function new_mlp

   ! Whole-array operations: matmul + elemental sigmoid do the loops for us.
   function mlp_forward(self, x) result(out)
      class(mlp), intent(inout) :: self
      real(real64), intent(in) :: x(:)
      real(real64) :: out(size(self%b2))

      self%hidden = sigmoid(matmul(x, self%w1) + self%b1)
      out = sigmoid(matmul(self%hidden, self%w2) + self%b2)
   end function mlp_forward

   function mlp_train_step(self, x, y) result(sq_err)
      class(mlp), intent(inout) :: self
      real(real64), intent(in) :: x(:), y(:)
      real(real64) :: out(size(y)), d_out(size(y)), d_hidden(size(self%b1))
      real(real64) :: sq_err

      out = self%forward(x)
      sq_err = sum((out - y)**2)                      ! elementwise array math

      d_out = (out - y)*out*(1.0_real64 - out)
      d_hidden = matmul(self%w2, d_out)*self%hidden*(1.0_real64 - self%hidden)

      ! Rank-1 weight updates expressed as outer products via matmul/reshape.
      self%w2 = self%w2 - self%lr*matmul( &
         reshape(self%hidden, [size(self%hidden), 1]), &
         reshape(d_out, [1, size(d_out)]))
      self%b2 = self%b2 - self%lr*d_out
      self%w1 = self%w1 - self%lr*matmul( &
         reshape(x, [size(x), 1]), &
         reshape(d_hidden, [1, size(d_hidden)]))
      self%b1 = self%b1 - self%lr*d_hidden
   end function mlp_train_step

end module neural_network_mod

program demo
   use, intrinsic :: iso_fortran_env, only: real64
   use neural_network_mod, only: mlp, new_mlp
   implicit none

   integer, parameter :: n_in = 4, n_hidden = 8, n_out = 2
   integer, parameter :: n_samples = 64, epochs = 1000
   real(real64), parameter :: lr = 0.5
   integer, parameter :: show_every = max(epochs/10, 1)

   type(mlp) :: net
   real(real64) :: x(n_samples, n_in), y(n_samples, n_out)
   real(real64) :: loss, sample_x(n_in), sample_y(n_out)
   integer :: epoch, s

   call random_init(repeatable=.true., image_distinct=.false.)  ! F2018
   net = new_mlp(n_in, n_hidden, n_out, lr)

   ! Toy dataset — replace with your own.
   call random_number(x)
   call random_number(y)

   do epoch = 1, epochs
      loss = 0.0_real64
      do s = 1, n_samples
         sample_x = x(s, :);  sample_y = y(s, :)
         loss = loss + net%train_step(sample_x, sample_y)
      end do
      if (mod(epoch, show_every) == 0) &
         print '(a, i5, a, f0.6)', 'epoch', epoch, '  mse = ', loss/n_samples
   end do
end program demo
