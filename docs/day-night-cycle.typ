= Day-Night Cycle Implementation
The day-night cycle in newer versions of MCprep is implemented with quadratic functions. They are:
$ 
  s(x) = -0.131x^2 + 2.959x - 10.946 \
  m(x) = cases(
  0.056x^2 - 2.152x + 21.487 "if" x >= 18,
  -0.036x^2 - 0.079x + 1.557 "if" x <= 5
  )
$

== Regression Implementation
MCprep uses a hand written regression algorithm for the following reasons:
- Less magic to developers
- Open, doesn't require owning a TI graphing calculator (which can cost hundreds of dollars)
- Consistency: 5 years from now this should have the same results as today, and not change

The steps MCprep's algorithm takes can be summerized with the following. Given 2 sets of size $n$, one holding $x$ values and one holding $y$ values, we can get a quadratic that closely matches what we want by solving the following system of equations:
$
  a sum x_i^4 + b sum x_i^3 + c sum x_i^2 = sum x_i^2 y_i \
  a sum x_i^3 + b sum x_i^2 + c sum x_i = sum x_i y_i \
  a sum x_i^2 + b sum x_i + c n = sum y_i
$
