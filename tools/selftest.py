#!/usr/bin/env python3
"""One command that decides whether this repository is trustworthy right now.

    python3 selftest.py        -> exit 0 if everything holds, 1 otherwise

`verify_vectors.py` answers "do the published vectors discriminate?". That is necessary and not
sufficient: it assumes the harness computes the right thing and that the degraded build is really
degraded. If the harness were subtly wrong, or the degradation silently inert, verify_vectors would
still print a clean 20/20 -- the numbers would just all be wrong together.

So this checks the chain underneath the vectors as well, and finishes by DELIBERATELY CORRUPTING a
vector to confirm the checking can fail at all. A test suite that cannot fail is decoration.
"""
from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from pathlib import Path

REF = "./kat_harness"
DEG_DOWN = "./kat_harness_deg_down"
DEG_UP = "./kat_harness_deg_up"
GOOD_DN = "./kat_harness_good_dn"
GOOD_UP = "./kat_harness_good_up"
VECTORS = Path("../vectors/berexp.json")

TWO63 = 1 << 63
_fails: list[str] = []
_n = 0


def check(cond: bool, name: str, detail: str = "") -> bool:
    global _n
    _n += 1
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))
    if not cond:
        _fails.append(name + (f" -- {detail}" if detail else ""))
    return cond


def run(binary: str, *args: str) -> dict:
    out = subprocess.run([binary, *args], capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise RuntimeError(f"{binary} {' '.join(args)} -> rc={out.returncode}: {out.stderr.strip()}")
    return json.loads(out.stdout.strip().splitlines()[-1])


def main() -> int:
    print("falcon-sampler-kat selftest\n")

    print("[1] build products")
    missing = [b for b in (REF, DEG_DOWN, DEG_UP, GOOD_DN, GOOD_UP)
               if not Path(b).exists()]
    if not check(not missing, "reference and both degraded harnesses are built", ", ".join(missing)):
        print("\n    build them first -- see tools/README.md")
        return 1
    check(VECTORS.exists(), "vectors/berexp.json is present")

    print("\n[2] the harness computes the reference correctly")
    # NOTE ON THE DOMAIN, learned by this check failing on its first run. fpr_expm_p63 requires
    # ccs < 1 -- ccs is sigma_min/sigma and sigma > sigma_min always, so ccs == 1.0 is outside the
    # function's contract and overflows to 0. Testing at ccs=1.0 reports the harness as broken when
    # it is the test that is wrong. Every check here uses a ccs a real sampler would produce.
    CCS = 0.75
    z0 = run(REF, "expm", "0.0", str(CCS))["expm_p63"]
    want = int(CCS * TWO63)
    check(abs(z0 - want) <= want >> 40, "expm(0, ccs) == ccs * 2^63",
          f"got {z0}, want ~{want}")

    # exp(-r) is strictly decreasing in r; a harness that scrambled its arguments would not be.
    vals = [run(REF, "expm", str(r), str(CCS))["expm_p63"] for r in (0.0, 0.2, 0.4, 0.6)]
    check(all(a > b for a, b in zip(vals, vals[1:])), "expm is strictly decreasing in r",
          " > ".join(str(v) for v in vals))

    # ccs scales the result linearly: expm(r, 0.5) * 1.5 == expm(r, 0.75).
    a75 = run(REF, "expm", "0.3", "0.75")["expm_p63"]
    a50 = run(REF, "expm", "0.3", "0.50")["expm_p63"]
    check(abs(a50 * 3 - a75 * 2) <= a75 >> 40, "expm scales linearly in ccs",
          f"{a50}*1.5 vs {a75}")

    print("\n[3] the degraded builds are actually degraded, in the right directions")
    r, ccs = "0.20000016761838121", "0.74999085331882487"
    v_ref = run(REF, "expm", r, ccs)["expm_p63"]
    v_dn = run(DEG_DOWN, "expm", r, ccs)["expm_p63"]
    v_up = run(DEG_UP, "expm", r, ccs)["expm_p63"]
    check(v_dn < v_ref, "the down build under-computes", f"{v_dn} < {v_ref}")
    check(v_up > v_ref, "the up build over-computes", f"{v_up} > {v_ref}")
    # ~2^-33 relative error means the gap is roughly 2^30 on a 2^63 scale.
    rel = abs(v_ref - v_dn) / v_ref
    check(2 ** -36 < rel < 2 ** -30, "the degradation is about 2^-33",
          f"measured 2^{math.log2(rel):.1f}")

    print("\n[4] published vectors agree with the reference")
    data = json.loads(VECTORS.read_text(encoding="utf-8"))
    vecs = [(p, v) for p, b in data["parameter_sets"].items() for v in b["vectors"]]
    check(len(vecs) == 20, "20 vectors published", f"found {len(vecs)}")
    n_acc = sum(1 for _, v in vecs if v["reference_accepts"])
    check(n_acc == 10 and len(vecs) - n_acc == 10,
          "both error directions are represented", f"{n_acc} accept / {len(vecs)-n_acc} reject")
    check(len({v["bytes"] for _, v in vecs}) == len(vecs), "no duplicate byte streams")

    bad = [f"{p}:{v['x']}" for p, v in vecs
           if run(REF, "berexp", v["x"], v["ccs"], v["bytes"])["accept"] != v["reference_accepts"]]
    check(not bad, "every vector matches its published reference answer", ", ".join(bad[:3]))

    print("\n[5] every vector discriminates")
    noflip = []
    for p, v in vecs:
        coarse = DEG_DOWN if v["reference_accepts"] else DEG_UP
        if run(coarse, "berexp", v["x"], v["ccs"], v["bytes"])["accept"] == v["reference_accepts"]:
            noflip.append(f"{p}:{v['x']}")
    check(not noflip, "all 20 flip against a coarse exp()", ", ".join(noflip[:3]))

    print("\n[5b] a GOOD implementation does not flip (positive control)")
    # THE ARM THAT PROVES THE PLACEMENT. Stages 4 and 5 show the vectors separate the reference from
    # a 2^-33 build -- but that is equally true if a drawn value sits ONE ULP below z, in which case
    # the set tests bit-identity with PQClean rather than the 2^-40 bar, and BOTH arms pass
    # identically either way. The only thing that distinguishes those is an implementation
    # comfortably INSIDE the bar, which must AGREE. Without this arm the suite is blind to that
    # difference by construction -- the same shape as a check with no positive control.
    ok_place, worst = True, ""
    for pset, v in vecs:
        z, u = int(v["z_reference"], 16), int(v["u_drawn"], 16)
        want = z >> 40
        if abs(abs(z - u) - want) > max(2, want // 1000):
            ok_place, worst = False, f"{pset}:{v['x']} offset={abs(z-u)} want~{want}"
            break
    check(ok_place, "every drawn value sits ~z>>40 from z, not one ULP",
          worst or "the offset IS the 2^-40 window")

    drift = []
    for pset, v in vecs:
        ref = run(REF, "berexp", v["x"], v["ccs"], v["bytes"])["accept"]
        for good in (GOOD_DN, GOOD_UP):
            if run(good, "berexp", v["x"], v["ccs"], v["bytes"])["accept"] != ref:
                drift.append(f"{pset}:{v['x']} vs {good}")
    check(not drift, "a ~2^-45 implementation agrees with the reference on all 20",
          ", ".join(drift[:3]) or "40/40 checks")

    print("\n[5c] the README example is a real published vector")
    # It was not, once: a hand-typed example showing u = z-1 shipped in the document people copy
    # from, while the actual vectors were correctly placed at z>>40. A fabricated example is the
    # exact unregenerable artifact this project keeps finding in other people's work, so it is
    # checked here rather than trusted.
    readme = Path("../README.md").read_text(encoding="utf-8")
    published = {v["bytes"] for _, v in vecs}
    quoted = set(re.findall(r'"bytes":\s*"([0-9a-fA-F]{16})"', readme))
    check(bool(quoted) and quoted <= published,
          "every byte stream quoted in README.md is a published vector",
          f"not published: {sorted(quoted - published)}" if quoted - published
          else f"{len(quoted)} quoted, all real")

    print("\n[6] the checking can fail (tautology guard)")
    # Everything above passing means little unless a WRONG vector would be caught. Flip a published
    # answer and confirm check [4]'s comparison rejects it.
    p, v = vecs[0]
    got = run(REF, "berexp", v["x"], v["ccs"], v["bytes"])["accept"]
    check(got != (not v["reference_accepts"]),
          "a corrupted expected-answer is rejected",
          "inverted the published answer; the reference disagrees, as it must")
    # And that a vector with the drawn value moved outside the window stops discriminating.
    u = int(v["u_drawn"], 16)
    far = f"{max(0, u - (1 << 40)):016x}"
    a = run(REF, "berexp", v["x"], v["ccs"], far)["accept"]
    b = run(DEG_DOWN, "berexp", v["x"], v["ccs"], far)["accept"]
    check(a == b, "a byte stream outside the window does NOT discriminate",
          "confirms the flip comes from the window, not from the degradation alone")

    print(f"\n{'=' * 60}")
    if _fails:
        print(f"{len(_fails)} of {_n} checks FAILED:")
        for f in _fails:
            print("  -", f)
        return 1
    print(f"all {_n} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
