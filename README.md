Python deductive stuck-at fault simulator for combinational netlists.

## What it does
- Parses a gate-level netlist, levelizes it, and simulates stuck-at-0/1 faults on every net using set-based fault-list propagation (controlling-value intersection/difference; symmetric difference for XOR/XNOR).
- Option (a): simulate all faults. Option (b): simulate only faults listed in a file (`net value` per line).
- Writes a report of detected faults and fault coverage.
- Random-vector mode with coverage-vs-vectors plot and CSV output.

## Usage
    python deductive_fsim.py CIRCUIT --vector BITS [--faults FILE] [--out FILE]
    python deductive_fsim.py CIRCUIT --random N --seed S --plot coverage.png

## Validation
Detected-fault lists match the course sample output and agree with an independent serial fault simulator and a bit-parallel simulator on all assigned vectors.

## Results (random vectors, 20-seed mean to reach coverage)
| Circuit | >75% | >90% |
|---|---|---|
| s27 | 9.9 | 19.6 |
| s298f_2 | 17.0 | 49.6 |
| s344f_2 | 8.9 | 22.4 |
| s349f_2 | 8.9 | 22.4 |

Full details are in `report.pdf`.
