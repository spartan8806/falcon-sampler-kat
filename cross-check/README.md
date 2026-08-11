# Cross-implementation check

The vectors in `../vectors/berexp.json` were generated against PQClean. On their own that leaves an
obvious question: do they test the **2⁻⁴⁰ precision bar**, or merely **bit-identity with PQClean**?

The only way to answer it is to run them against a different implementation. Two were used, and they
are the two that matter: a correct one that must agree, and the *actual historical defect* that must
be caught.

## Results

| implementation | arithmetic | result |
|---|---|---|
| PQClean falcon-512 `clean` | `uint64_t` software float (`fpr`) | source of the expected answers |
| **falcon-rust v0.3.0** (post-fix) | `FixedPoint128` | **20/20 agree** |
| **falcon-rust v0.1.3** (GHSA-25rm-9wvm-m38v) | `FixedPoint64`, ~2⁻³³ | **10/20 caught the defect** |

Two independent codebases, different languages, different fixed-point representations, no shared
lineage in the arithmetic — and identical accept/reject on every vector. That is the claim the KAT
set needs to make, and it is now measured rather than argued.

## The 10/20 is the expected number, not a shortfall

Each `x` appears twice: one vector that flips if `exp()` **under**-computes, one if it
**over**-computes. For a given implementation at a given `x`, the error runs one way, so exactly one
of the pair flips. Ten vectors caught across ten parameter points means **every point was caught** —
by whichever vector happened to be pointed the right way.

## The real defect errs in BOTH directions, which was a guess until now

Both error directions are published because a coarse approximation is not guaranteed to err low. That
was a design assumption. v0.1.3 confirms it:

```
Falcon-512   x=0.05   reference=false  v0.1.3=true    <- over-computes here
Falcon-512   x=0.35   reference=true   v0.1.3=false   <- under-computes here
Falcon-1024  x=0.05   reference=true   v0.1.3=false   <- under
Falcon-1024  x=0.50   reference=false  v0.1.3=true    <- over
```

The same implementation errs in opposite directions at different `x`. **A one-sided vector set would
have missed half of these**, and would have looked perfectly healthy doing it.

## Reproducing

`falcon-rust`'s `ber_exp` is module-private, so the test has to live inside its crate — the same
reason the C harness `#include`s `sign.c`. Driving it through the public API would exercise the
sampler plumbing instead of the arithmetic the vectors are about.

The two injected tests are kept here verbatim:

- `falcon_rust_v0.3.0_agrees.rs.txt` — paste into the `#[cfg(test)]` module of
  `falcon-rust/src/samplerz.rs` at `v0.3.0`, then
  `cargo test --release falcon_sampler_kat_cross_check -- --nocapture`
- `falcon_rust_v0.1.3_caught.rs.txt` — same, at tag `v0.1.3` (note `FixedPoint64`, not `128`), then
  `cargo test --release falcon_sampler_kat_catches_the_defect -- --nocapture`

Note that `falcon-rust`'s `ber_exp` takes **seven** bytes where PQClean's consumes up to eight. Every
published vector's first divergence from `z` falls at byte index 4 or 5 — the offset is `z >> 40`,
about 2²³, which perturbs the lower-middle bytes — so seven is sufficient. The generator checks this
rather than assuming it and would refuse to emit a vector whose divergence fell outside that window.

## What this does not settle

- Two implementations, not five. Agreement across more lineages would be worth more, and contributions
  of results from other implementations are welcome.
- v0.1.3 is one under-provisioned implementation. Another coarse sampler could err differently and be
  caught by a different subset — or, if its error were smaller than 2⁻⁴⁰, correctly not caught at all.
- These runs used the vectors as published. They are not a re-derivation of the expected answers from
  `falcon-rust`; PQClean remains the source of the expected values.
