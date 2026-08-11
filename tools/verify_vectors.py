#!/usr/bin/env python3
"""Prove every published vector discriminates: reference one way, coarse exp() the other.

A vector the reference accepts proves only that the reference behaves as constructed. The claim the
document actually makes is that these vectors CATCH an under-provisioned sampler -- and that is only
demonstrated by running the identical vector through a coarse implementation and seeing it flip.

Two builds of the same harness are used: the stock one, and one where fpr_expm_p63's low bits are
cleared to simulate a given precision. Nothing else differs, so a flip is attributable to precision
alone.

    ./verify_vectors.py                # whatever degraded build is on disk; it measures which

There is deliberately NO precision argument, and no hardcoded precision either. Both have been
tried and both went wrong the same way:

  - The ARGUMENT only changed the number printed. `verify_vectors.py 18` reported "20/20
    discriminate at ~2^-45" while running the identical 2^-33 binaries -- a claim selftest.py
    disproves one file away, since a real 2^-45 build agrees with the reference on all 20.
  - Removing it and keeping `DEGRADED_AT = 33` fixed the symptom and left the cause. Following
    tools/README's own instruction -- rebuild the degraded harnesses at another -DDEGRADE_BITS --
    then printed "~2^-33" against 2^-45 binaries.

The script now MEASURES the relative error of the binaries in front of it and reports that. To test
another precision, rebuild at that -DDEGRADE_BITS and re-run; the reported figure follows.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

#: NOTHING HERE IS HARDCODED ANY MORE, and the reason is worth keeping.
#:
#: This file used to carry `DEGRADED_AT = 33` and print "~2^-33" unconditionally. tools/README tells
#: the reader that to check another precision they should rebuild the degraded harnesses at a
#: different -DDEGRADE_BITS and re-run. Doing exactly that produced:
#:
#:     reference vs a sampler whose exp() carries ~2^-33 relative error
#:       Falcon-512   0/10 vectors flip
#:
#: against 2^-45 binaries. The number was a stale label describing a build that was no longer on
#: disk -- the same defect as the precision ARGUMENT removed from this script on 2026-08-14, which
#: also only changed the number it printed. Removing the argument and keeping a constant fixed the
#: symptom and left the cause.
#:
#: So the script now MEASURES the degradation it is actually running, from the binaries in front of
#: it, and reports that. A label that cannot go stale is one that is derived rather than declared.


def run(binary: str, *args: str) -> dict:
    out = subprocess.run([binary, *args], capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise RuntimeError(f"{binary} {args} failed: {out.stderr.strip()}")
    return json.loads(out.stdout.strip().splitlines()[-1])


def main() -> int:
    if len(sys.argv) > 1:
        print(f"error: {sys.argv[0]} takes no arguments. It reports the precision it MEASURES from "
              f"the binaries on disk, so there is nothing to select. Rebuild the degraded harnesses "
              f"at another -DDEGRADE_BITS to test another level.", file=sys.stderr)
        return 2
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

    # MEASURE the degradation actually on disk, worst case over the published inputs, instead of
    # printing a constant. |z_ref - z_deg| / z_ref is the relative error the build really carries;
    # the largest one is what decides whether a vector can flip.
    worst = 0.0
    for _pset, _blk in data["parameter_sets"].items():
        for _v in _blk["vectors"]:
            zr = run(ref, "berexp", _v["x"], _v["ccs"], _v["bytes"])["z"]
            zd = run(deg_down if _v["reference_accepts"] else deg_up,
                     "berexp", _v["x"], _v["ccs"], _v["bytes"])["z"]
            if zr:
                worst = max(worst, abs(zr - zd) / zr)
    measured = f"2^{math.log2(worst):.2f}" if worst else "0 (THE DEGRADATION IS INERT)"
    print(f"reference vs the degraded build on disk: measured worst-case relative error {measured}\n")
    if not worst:
        print("error: the degraded binaries produce identical output to the reference. Every vector "
              "would 'discriminate' vacuously. Rebuild them.", file=sys.stderr)
        return 1

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

    print(f"\n{flipped}/{total} vectors discriminate against a build measured at {measured}")
    if failures:
        print(f"\n{len(failures)} PROBLEM(S) -- do not publish these:")
        for f in failures:
            print("  -", f)
        return 1
    print("every published vector is confirmed in BOTH directions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
