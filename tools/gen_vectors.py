#!/usr/bin/env python3
"""Generate and verify BerExp KAT vectors that trip an under-provisioned Falcon sampler.

CONSTRUCTION, NOT SEARCH. BerExp accepts iff the drawn 64-bit big-endian value u is strictly less
than

    z = ((fpr_expm_p63(r, ccs) << 1) - 1) >> s

compared MSB-first (falcon reference, sign.c). An implementation whose exp() carries relative error
eps computes z' ~= z*(1 +/- eps). So placing u inside the window between z and z*(1 - 2^-40) makes
the acceptance decision a direct test of whether exp() is accurate to 2^-40:

    u = z - ceil(z * 2^-40)      reference (err ~2^-51) ACCEPTS; any impl that UNDER-computes
                                 exp by more than 2^-40 REJECTS.
    u = z + floor(z * 2^-40)     reference REJECTS (u >= z); any impl that OVER-computes exp by
                                 more than 2^-40 ACCEPTS.

Both directions are published because a coarse approximation is not guaranteed to err low. A vector
set containing only the first kind would silently pass an implementation whose error runs the other
way -- the same one-sided-test mistake this whole finding is about.

The 2^-40 figure is NOT from the Falcon specification, which stipulates no precision floor. It comes
from Prest'17 and Howe-Prest-Ricosset-Rossi'19, whose analyses identify ~2^-40 relative precision as
the premise the security proof needs. See README.md.

Every expected value here is produced by PQClean's own sign.c/fpr.c via the harness -- never by this
script's arithmetic. This script only chooses u and records what the reference did.
"""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path

HARNESS = "./kat_harness"

# sigma_min per parameter set, from the Falcon specification (Table 3.3).
PARAM_SETS = {
    "Falcon-512": 1.277833697,
    "Falcon-1024": 1.298280334,
}


def harness(*args: str) -> dict:
    out = subprocess.run([HARNESS, *args], capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise RuntimeError(f"harness {args} failed: {out.stderr.strip()}")
    return json.loads(out.stdout.strip().splitlines()[-1])


def u64_be_hex(u: int) -> str:
    return f"{u:016X}".lower()


def make_vector(x: float, ccs: float, direction: str) -> dict:
    """Build one vector at the 2^-40 discrimination threshold and CONFIRM it on the reference."""
    probe = harness("berexp", repr(x), repr(ccs), "00" * 8)
    z = probe["z"]
    if z == 0:
        raise ValueError("z == 0; pick a different x")

    gap = max(1, math.ceil(z * 2 ** -40))
    if direction == "accept":            # reference accepts, coarse-under rejects
        u = z - gap
    else:                                # reference rejects, coarse-over accepts
        u = z + gap - 1
        if u >= 1 << 64:
            raise ValueError("u overflows 64 bits; pick a different x")

    got = harness("berexp", repr(x), repr(ccs), u64_be_hex(u))
    expected_accept = 1 if direction == "accept" else 0
    if got["accept"] != expected_accept:
        raise AssertionError(
            f"CONSTRUCTION FAILED for x={x!r} ccs={ccs!r} dir={direction}: "
            f"reference returned accept={got['accept']}, expected {expected_accept}. "
            "The vector is not published unless the reference agrees.")
    return {
        "x": repr(x),
        "ccs": repr(ccs),
        "bytes": u64_be_hex(u),
        "z_reference": f"{z:#018x}",
        "u_drawn": f"{u:#018x}",
        "reference_accepts": bool(got["accept"]),
        "discriminates_at": "2^-40",
        "flips_if": ("exp() under-computes by more than 2^-40"
                     if direction == "accept" else
                     "exp() over-computes by more than 2^-40"),
        "s": got["s"],
        "r": got["r"],
    }


def main() -> int:
    if not Path(HARNESS).exists():
        print(f"error: {HARNESS} not built. See tools/README.md", file=sys.stderr)
        return 1

    out: dict = {
        "format": "falcon-sampler-kat.berexp.v1",
        "generated_against": "PQClean falcon-512 clean (sign.c BerExp, fpr.c fpr_expm_p63)",
        "precision_threshold": "2^-40 relative error in exp(), per Prest'17 / HPRR'19",
        "note": ("The Falcon specification stipulates no precision floor. These vectors test the "
                 "premise the security proof requires, not a spec conformance requirement."),
        "parameter_sets": {},
    }

    # x values spread across [0, log 2), which is the interval BerExp reduces into, so the vectors
    # exercise different regions of the polynomial rather than clustering at one point.
    xs = [0.05, 0.20000016761838121, 0.35, 0.5, 0.65]
    total = 0
    for name, sigma_min in PARAM_SETS.items():
        ccs = sigma_min / 1.8         # a representative sigma in Falcon's 1.2-1.9 range
        vectors = []
        for x in xs:
            for direction in ("accept", "reject"):
                try:
                    vectors.append(make_vector(x, ccs, direction))
                except (ValueError, AssertionError) as exc:
                    print(f"  skipped x={x} {direction}: {exc}", file=sys.stderr)
        out["parameter_sets"][name] = {"sigma_min": repr(sigma_min), "ccs_used": repr(ccs),
                                       "vectors": vectors}
        total += len(vectors)
        print(f"{name}: {len(vectors)} vectors confirmed against the reference")

    dest = Path("../vectors/berexp.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {dest} ({total} vectors)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
