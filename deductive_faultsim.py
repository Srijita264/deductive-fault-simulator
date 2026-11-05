import argparse
import os
import random
import sys

CONTROLLING = {'AND': 0, 'NAND': 0, 'OR': 1, 'NOR': 1}
ALIAS = {'INV': 'NOT', 'BUF': 'BUFF'}

ASSIGNMENT_VECTORS = {
    's27': ['1101101', '0101001'],
    's298f_2': ['10101011110010101', '11101110101110111'],
    's344f_2': ['101010101010111101111111', '111010111010101010001100'],
    's349f_2': ['101000000010101011111111', '111111101010101010001111'],
}


def parse_netlist(path):
    pis, pos, gates = [], [], []
    with open(path) as f:
        for line in f:
            t = [x for x in line.upper().split() if x != '-1']
            if not t:
                continue
            if t[0] == 'INPUT':
                pis += t[1:]
            elif t[0] == 'OUTPUT':
                pos += t[1:]
            elif len(t) >= 3:
                gates.append((ALIAS.get(t[0], t[0]), t[-1], t[1:-1]))
            else:
                raise ValueError(f'{path}: cannot parse line: {line.strip()}')
    known, order, pending = set(pis), [], gates
    while pending:
        ready = [g for g in pending if all(i in known for i in g[2])]
        if not ready:
            raise ValueError(f'{path}: undriven net or combinational loop near {pending[:3]}')
        known |= {g[1] for g in ready}
        order += ready
        pending = [g for g in pending if g not in ready]
    return {'name': os.path.basename(path), 'PI': pis, 'PO': pos, 'gates': order,
            'nets': set(pis) | {g[1] for g in order}}


def all_faults(c):
    return {(n, s) for n in c['nets'] for s in (0, 1)}


def read_fault_file(path, c):
    faults = set()
    with open(path) as f:
        for k, line in enumerate(f, 1):
            t = line.split('#')[0].split()
            if not t:
                continue
            if len(t) != 2 or t[1] not in ('0', '1') or t[0] not in c['nets']:
                print(f'warning: {path} line {k} ignored: {line.strip()!r}', file=sys.stderr)
                continue
            faults.add((t[0], int(t[1])))
    return faults


def gate_value(g, v):
    if g == 'AND': return int(all(v))
    if g == 'NAND': return 1 - int(all(v))
    if g == 'OR': return int(any(v))
    if g == 'NOR': return 1 - int(any(v))
    if g == 'NOT': return 1 - v[0]
    if g == 'BUFF': return v[0]
    p = sum(v) % 2
    if g == 'XOR': return p
    if g == 'XNOR': return 1 - p
    raise ValueError(f'unknown gate type {g}')


def propagate(g, vals, lists):
    if g in CONTROLLING:
        c = CONTROLLING[g]
        at_c = [i for i, x in enumerate(vals) if x == c]
        if at_c:
            out = set.intersection(*[lists[i] for i in at_c])
            for i, x in enumerate(vals):
                if x != c:
                    out = out - lists[i]
            return out
        return set().union(*lists)
    if g in ('XOR', 'XNOR'):
        out = set()
        for l in lists:
            out = out ^ l
        return out
    return set(lists[0])


def simulate_vector(c, vec, targets=None):
    if len(vec) != len(c['PI']):
        raise ValueError(f"{c['name']}: vector has {len(vec)} bits but circuit has {len(c['PI'])} inputs")
    val, flist = {}, {}
    for n, b in zip(c['PI'], vec):
        val[n] = b
        flist[n] = {(n, 1 - b)}
    for g, out, ins in c['gates']:
        v = [val[i] for i in ins]
        val[out] = gate_value(g, v)
        flist[out] = propagate(g, v, [flist[i] for i in ins]) | {(out, 1 - val[out])}
    detected = set().union(*[flist[o] for o in c['PO']])
    return detected & targets if targets is not None else detected


def parse_vector(s):
    s = s.replace(' ', '')
    if not s or any(ch not in '01' for ch in s):
        raise ValueError(f'bad vector: {s!r}')
    return [int(ch) for ch in s]


def fault_key(f):
    return (int(f[0]) if f[0].isdigit() else 0, f[0], f[1])


def write_report(path, circuit, vectors, detected, total):
    with open(path, 'w') as f:
        f.write(f'Circuit: {circuit}  Input Vector(s): {" ".join(vectors)}\n')
        f.write('------FAULTS DETECTED------\n')
        for n, s in sorted(detected, key=fault_key):
            f.write(f'{n:>5} stuck at {s}\n')
        f.write(f'\nNumber of faults detected: {len(detected)}\n')
        f.write(f'Number of faults simulated: {total}\n')
        f.write(f'Fault coverage: {100.0 * len(detected) / total:.2f}%\n')


def run_vectors(c, vectors, targets, out_path):
    total_set = targets if targets is not None else all_faults(c)
    detected = set()
    for v in vectors:
        detected |= simulate_vector(c, parse_vector(v), targets)
    write_report(out_path, c['name'], vectors, detected, len(total_set))
    print(f"{c['name']} vector(s) {' '.join(vectors)}: {len(detected)} of {len(total_set)} faults detected "
          f"({100.0 * len(detected) / len(total_set):.1f}%) -> {out_path}")
    return detected


def random_coverage(c, n_vectors, seed, targets=None):
    rnd = random.Random(seed)
    total = len(targets) if targets is not None else 2 * len(c['nets'])
    detected, cov = set(), []
    for _ in range(n_vectors):
        vec = [rnd.randint(0, 1) for _ in c['PI']]
        detected |= simulate_vector(c, vec, targets)
        cov.append(100.0 * len(detected) / total)
    return cov


def first_above(cov, pct):
    return next((k + 1 for k, x in enumerate(cov) if x > pct), None)


def do_random(c, args, targets):
    cov = random_coverage(c, args.random, args.seed, targets)
    print(f"{c['name']}: {len(cov)} random vectors (seed {args.seed}), final coverage {cov[-1]:.2f}%")
    for pct in (75, 90):
        k = first_above(cov, pct)
        print(f"  >{pct}% coverage first reached at vector {k}" if k else f"  >{pct}% coverage not reached")
    if args.csv:
        with open(args.csv, 'w') as f:
            f.write('vectors,coverage_percent\n')
            for k, x in enumerate(cov, 1):
                f.write(f'{k},{x:.4f}\n')
    if args.plot:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        plt.figure(figsize=(7, 4.5))
        plt.plot(range(1, len(cov) + 1), cov, label=c['name'])
        for pct in (75, 90):
            plt.axhline(pct, color='gray', ls='--', lw=0.8)
        plt.xscale('log'); plt.xlabel('Number of random vectors'); plt.ylabel('Fault coverage (%)')
        plt.grid(True); plt.legend(); plt.tight_layout(); plt.savefig(args.plot, dpi=200)
        print(f'  plot saved to {args.plot}')


def main():
    ap = argparse.ArgumentParser(description='Deductive fault simulator (ECE 6140 Project 2)')
    ap.add_argument('circuit', nargs='?', help='netlist file')
    ap.add_argument('--vector', action='append', default=[], help='input vector, e.g. 1101101 (repeatable)')
    ap.add_argument('--vectors-file', help='file with one vector per line')
    ap.add_argument('--faults', help='option (b): fault list file ("net value" per line)')
    ap.add_argument('--out', help='output file (default <circuit>_out.txt)')
    ap.add_argument('--random', type=int, metavar='N', help='apply N random vectors and report coverage')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--plot', help='save coverage plot (PNG) for --random')
    ap.add_argument('--csv', help='save coverage vs vectors (CSV) for --random')
    ap.add_argument('--assignment', metavar='DIR', help='run all 8 Part (a) vectors on the netlists in DIR')
    args = ap.parse_args()

    if args.assignment:
        for name, vecs in ASSIGNMENT_VECTORS.items():
            c = parse_netlist(os.path.join(args.assignment, name + '.txt'))
            for i, v in enumerate(vecs, 1):
                run_vectors(c, [v], None, os.path.join(args.assignment, f'{name}_v{i}_out.txt'))
        return

    if not args.circuit:
        ap.error('circuit file required')
    c = parse_netlist(args.circuit)
    targets = read_fault_file(args.faults, c) if args.faults else None

    if args.random:
        do_random(c, args, targets)
        return

    vectors = list(args.vector)
    if args.vectors_file:
        with open(args.vectors_file) as f:
            vectors += [l.strip() for l in f if l.strip()]
    if not vectors:
        ap.error('give --vector, --vectors-file, or --random')
    out = args.out or os.path.splitext(args.circuit)[0] + '_out.txt'
    run_vectors(c, vectors, targets, out)


if __name__ == '__main__':
    main()
