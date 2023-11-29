from typing import List
import numpy as np

# We implement our own version of quadratic 
# regression for 3 reasons:
# - Less magic
# - Open, doesn't require owning a 
#   graphing calculator
# - Consistency: 5 years from now this 
#   should have the same results as today,
#   and not change
def quadratic_regression(points: List):
	sum_x = sum([x for x, _ in points])
	sum_y = sum([y for _, y in points])
	sum_x_squared = sum([x*x for x, _ in points])
	sum_x_cubed = sum([x*x*x for x, _ in points])
	sum_x_quartic = sum([x*x*x*x for x, _ in points])
	sum_x_y = sum([x*y for x, y in points])
	sum_x_squared_y = sum([(x*x)*y for x, y in points])
	n = len(points)

	coefficients = np.array([
		[sum_x_quartic, sum_x_cubed, sum_x_squared],
		[sum_x_cubed, sum_x_squared, sum_x],
		[sum_x_squared, sum_x, n]
	])
	answers = np.array([
		sum_x_squared_y,
		sum_x_y,
		sum_y
	])
	return np.linalg.solve(coefficients, answers)

# Ideal X and Y points for 
# the daylight cycle
SCY_IDEAL: List = [
	(5, 0),
	(6, 3),
	(10, 5),
	(12, 6),
	(14, 5),
	(16, 3),
	(18, 0)
]

SCY_QUAD = [round(n, 3) for n in quadratic_regression(SCY_IDEAL)]
print("Sun Cycle", "-"*10)
print(f"scy(x) = {SCY_QUAD[0]}x^2 + {SCY_QUAD[1]}x + {SCY_QUAD[2]}")
for x, y in SCY_IDEAL:
	print(f"scy({x}) = ({y} ideal) ({SCY_QUAD[0]*(x*x) + SCY_QUAD[1]*x + SCY_QUAD[2]})")

# Ideal X and Y points for 
# first half of night cycle
MCY_IDEAL_1: List = [
	(18, 0.2),
	(19, 0.4),
	(20, 0.8),
	(21, 1),
	(22, 1.2),
	(23, 1.4),
	(18, 1.6)
]

MCY_QUAD_1 = [round(n, 3) for n in quadratic_regression(MCY_IDEAL_1)]
print("\nMoon Cycle (first half)", "-"*10)
print(f"mcy_1(x) = {MCY_QUAD_1[0]}x^2 + {MCY_QUAD_1[1]}x + {MCY_QUAD_1[2]}")
for x, y in MCY_IDEAL_1:
	print(f"mcy_1({x}) = ({y} ideal) ({MCY_QUAD_1[0]*(x*x) + MCY_QUAD_1[1]*x + MCY_QUAD_1[2]})")

# Ideal X and Y points for 
# second half of night cycle
MCY_IDEAL_2: List = [
	(0, 1.6),
	(1, 1.4),
	(2, 1.2),
	(3, 1),
	(4, 0.8),
	(5, 0.2)
]

MCY_QUAD_2 = [round(n, 3) for n in quadratic_regression(MCY_IDEAL_2)]
print("\nMoon Cycle (second half)", "-"*10)
print(f"mcy_2(x) = {MCY_QUAD_2[0]}x^2 + {MCY_QUAD_2[1]}x + {MCY_QUAD_2[2]}")
for x, y in MCY_IDEAL_2:
	print(f"mcy_2({x}) = ({y} ideal) ({MCY_QUAD_2[0]*(x*x) + MCY_QUAD_2[1]*x + MCY_QUAD_2[2]})")
