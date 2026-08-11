#!/usr/bin/env python3
"""Prove every published vector discriminates: reference one way, coarse exp() the other.

A vector the reference accepts proves only that the reference behaves as constructed. The claim the
document actually makes is that these vectors CATCH an under-provisioned sampler -- and that is only
demonstrated by running the identical vector through a coarse implementation and seeing it flip.

Two builds of the same harness are used: the stock one, and one where fpr_expm_p63's low bits are
cleared to simulate a given precision. Nothing else differs, so a flip is attributable to precision
alone.

    ./verify_vectors.py                # reference vs 2^-33 (the falcon-rust GHSA-25rm level)
    ./verify_vectors.py 26             # a milder degradation
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def run(binary: str, *args: str) -> dict:
    out = subprocess.run([binary, *args], capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise RuntimeError(f"{binary} {args} failed: {out.stderr.strip()}")
    return json.loads(out.stdout.strip().splitlines()[-1])


def main() -> int:
    degrade_bits = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    approx_precision = 63 - degrade_bits
    ref = "./kat_harness"
    # An accept-vector is tripped by an implementation that UNDER-computes exp; a
    # reject-vector by one that OVER-computes. Each is checked against the degradation that
    # can actually exercise it -- testing both against one direction certifies half the set
    # as useless, which is exactly what the first run of this script did.
    deg_down, deg_up = "./kat_harness_deg_down", "./kat_harness_deg_up"
    for b in (ref, deg_down, deg_up):
        if not Path(b).exists():
            print(f"error: {b} not built -- see tools/README.md", file=sys.stderr)
            return 1

    data = json.loads(Path("../vectors/berexp.json").read_text(encoding="utf-8"))
    print(f"reference vs a sampler whose exp() carries ~2^-{approx_precision} relative error\n")

    total = flipped = 0
    failures = []
    for pset, block in data["parameter_sets"].items():
        n_flip = 0
        for v in block["vectors"]:
            total += 1
            a = run(ref, "berexp", v["x"], v["ccs"], v["bytes"])["accept"]
            coarse = deg_down if v["reference_accepts"] else deg_up
            b = run(coarse, "berexp", v["x"], v["ccs"], v["bytes"])["accept"]
            if a != v["reference_accepts"]:
                failures.append(f"{pset} x={v['x']}: reference disagrees with the published value")
                continue
            if a != b:
                n_flip += 1
                flipped += 1
            else:
                failures.append(
                    f"{pset} x={v['x']} dir={'accept' if v['reference_accepts'] else 'reject'}: "
                    f"did NOT flip (both {a}) against {coarse} -- does not discriminate here")
        print(f"  {pset:12} {n_flip}/{len(block['vectors'])} vectors flip")

    print(f"\n{flipped}/{total} vectors discriminate at ~2^-{approx_precision}")
    if failures:
        print(f"\n{len(failures)} PROBLEM(S) -- do not publish these:")
        for f in failures:
            print("  -", f)
        return 1
    print("every published vector is confirmed in BOTH directions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
