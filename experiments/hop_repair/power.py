"""Discrete effect-size table for §13 (PREREGISTRATION.md §13.5). Exact, no simulation.

    uv run python experiments/hop_repair/power.py

Each eligible pair (initial incomplete) ends as T_only, C_only, Both or Neither. The primary
rule: over the pooled Caddy + File Browser pairs, the one-sided exact sign test on the
discordant pairs (T_only vs C_only) gives p <= ALPHA, and in each fixture T_only >= C_only.
"""

from itertools import product
from math import comb

ALPHA = 0.05


def sign_p(t: int, c: int) -> float:
    d = t + c
    return sum(comb(d, k) for k in range(t, d + 1)) / 2 ** d if d else 1.0


def fixture_dist(k: int, pt: float, pc: float) -> dict[tuple[int, int], float]:
    """P(T_only = t, C_only = c) for k independent pairs."""
    out = {}
    for t, c in product(range(k + 1), repeat=2):
        if t + c <= k:
            rest = k - t - c
            out[(t, c)] = (comb(k, t) * comb(k - t, c) * pt ** t * pc ** c
                           * (1 - pt - pc) ** rest)
    return out


def success(tc1: tuple[int, int], tc2: tuple[int, int]) -> bool:
    t, c = tc1[0] + tc2[0], tc1[1] + tc2[1]
    return sign_p(t, c) <= ALPHA and tc1[0] >= tc1[1] and tc2[0] >= tc2[1]


def power(k: int, pt: float, pc: float) -> float:
    d = fixture_dist(k, pt, pc)
    return sum(p1 * p2 for a, p1 in d.items() for b, p2 in d.items() if success(a, b))


def main() -> None:
    print("minimum T_only for p <= 0.05 given d discordant pairs:")
    for d in range(1, 16):
        need = next((t for t in range(d + 1) if sign_p(t, d - t) <= ALPHA), None)
        print(f"  d={d:2}: T_only >= {need}" if need is not None else f"  d={d:2}: impossible")
    scenarios = [(0.00, 0.00), (0.10, 0.10), (0.15, 0.05), (0.25, 0.05), (0.35, 0.05), (0.50, 0.05)]
    print("\nP(SUCCESS) by eligible pairs per fixture K (pooled 2K) and (P(T_only), P(C_only)):")
    print("   K  " + "  ".join(f"({pt:.2f},{pc:.2f})" for pt, pc in scenarios))
    for k in (6, 8, 10, 12, 15):
        print(f"  {k:2}  " + "  ".join(f"{power(k, pt, pc):11.3f}" for pt, pc in scenarios))


if __name__ == "__main__":
    main()
