# Day-Night Cycle Implementation
The day-night cycle in newer versions of MCprep is implemented with quadratics, 3 to be exact. They are:
$scy(x)=-0.105x^2+2.511x-9.265$
$mfh(x)=-0.014x^2+0.831x-10.166$
$mlh(x)=-0.012x^2-0.146x+1.590$

$scy(x)$ represents the sun cycle, $mfh(x)$ represents the first half of the moon cycle, and $mlh(x)$ represents the latter half of the moon cycle.

To derive these quadratics, the following was done:
- Step 1. Create a set of points representing prefered values
- Step 2. Use those in quadrtic regression
- Step 3. Round $a$, $b$, and $c$ to 3 decimal places

The points used to derive each quadratic are the following:

|     scy(x)      |
| x      | y      |
|--------|--------|
| 5      | 0      |
| 6      | 3      |
| 10     | 5      |
| 12     | 6      |
| 14     | 5      |
| 18     | 3      |
| 19     | 0      |

|     mfh(x)      |
| x      | y      |
|--------|--------|
| 18     | 0.2    |
| 19     | 0.4    |
| 20     | 0.8    |
| 21     | 1      |
| 22     | 1.2    |
| 23     | 1.4    |

|     mfh(x)      |
| x      | y      |
|--------|--------|
| 0      | 1.6    |
| 1      | 1.4    |
| 2      | 1.2    |
| 3      | 1      |
| 4      | 0.8    |
| 5      | 0.2    |

