# Falcon sampler precision KATs

Known-answer test vectors that catch a Falcon implementation whose `exp()` approximation is
under-provisioned — the defect class behind
[GHSA-25rm-9wvm-m38v](https://github.com/aszepieniec/falcon-rust/security/advisories/GHSA-25rm-9wvm-m38v).

**The official Falcon KATs do not catch this.** That is the whole reason these exist. A sampler
running at ~2⁻³³ precision instead of ~2⁻⁵¹ still reproduces every published test vector, because the
defect changes `sampler_z`'s output only when the acceptance probability error flips a single
rejection decision — about 2⁻³³ per sample. Catching that with random outputs needs ~2³³ of them, so
no feasible set of end-to-end vectors reliably trips it.

These vectors sidestep that by testing the arithmetic directly, at the point where the error is
deterministic rather than probabilistic.

## What is actually being tested

Falcon's `BerExp` accepts iff the drawn 64-bit big-endian value `u` is strictly less than

```
z = ((expm_p63(r, ccs) << 1) - 1) >> s
```

compared most-significant-byte first. An implementation whose `exp()` carries relative error ε
computes `z' ≈ z·(1 ± ε)`. Each vector places `u` inside the window between `z` and `z·(1 ± 2⁻⁴⁰)`,
so the accept/reject answer *is* a measurement of whether `exp()` is accurate to 2⁻⁴⁰.

They are built by construction, not by search.

## On "required" precision — an important correction

**The Falcon specification stipulates no minimum precision.** An implementation running at 2⁻³³ is
within the letter of the spec.

The 2⁻⁴⁰ figure comes from the later analyses — [Prest'17] and [Howe–Prest–Ricosset–Rossi'19] — which
formalised the informal argument in the NIST proposal and identified ~2⁻⁴⁰ relative precision as the
premise the security proof needs. Falling below it does not violate the spec; it invalidates the
proof's precondition, so the proof no longer applies.

This distinction is due to [@aszepieniec](https://github.com/aszepieniec), who corrected it in the
advisory thread, and it is preserved here deliberately. These vectors test a security-refinement
premise, not spec conformance.

## Using them

`vectors/berexp.json` carries 20 vectors, 10 per parameter set. Each gives `(x, ccs, bytes)` and the
answer a correctly-provisioned implementation must return:

```json
{
  "x": "0.20000016761838121",
  "ccs": "0.70990760944444447",
  "bytes": "9d31c1a6e0cb8adc",
  "z_reference": "0x9d31c1a6e0cb8add",
  "reference_accepts": true,
  "discriminates_at": "2^-40",
  "flips_if": "exp() under-computes by more than 2^-40"
}
```

Feed `x`, `ccs` and the byte stream to your `BerExp` (or whatever your implementation calls the
Bernoulli-with-probability-exp(−x) step) and compare the accept/reject result. A disagreement on any
vector means your `exp()` is outside 2⁻⁴⁰ in that direction.

**Both error directions are covered.** Ten vectors trip an implementation that under-computes `exp`,
ten trip one that over-computes. A set containing only one kind would silently pass an implementation
whose error runs the other way — the same one-sided-test mistake this whole finding is about.

## Why these are `BerExp` vectors and not full `sampler_z` vectors

A full `sampler_z` vector — `(σ_min, μ, σ, bytes) → z` — **is not portable between implementations**,
and this was measured rather than assumed.

Running the `sampler_z` vector from the advisory thread against PQClean's reference returns `z = 101`,
where falcon-rust returns `102` (coarse) / `100` (reference). The cause is not precision at all:
PQClean's `gaussian0_sampler` draws nine bytes as a little-endian `u64` plus one, producing `z0 = 0`
from that stream, where falcon-rust derives `z0 = 1` from the identical bytes.

**The PRNG-to-`z0` mapping is an implementation detail, not fixed by the specification.** So a full
`sampler_z` vector tests one implementation's byte-consumption convention as much as its arithmetic,
and cannot serve as a universal KAT. `BerExp` has no such freedom: `(x, ccs) → z` and the MSB-first
comparison are arithmetic every implementation must agree on.

If you want end-to-end `sampler_z` vectors for your own implementation, `tools/kat_harness.c` will
generate them against your byte-consumption convention — but they belong in your test suite, not in a
cross-implementation KAT set.

## Provenance

Every expected value is produced by **PQClean's own `sign.c` / `fpr.c`**, not by a reimplementation.
`tools/kat_harness.c` `#include`s the reference `sign.c` so that `BerExp` itself computes the answers;
a transcription error cannot reach the vectors.

Each vector is confirmed in **both** directions before publication:

- the reference produces the published answer, and
- a build whose `exp()` low bits are cleared to ~2⁻³³ produces the opposite answer.

`tools/verify_vectors.py` re-checks all 20 and refuses to pass if any vector fails either half.

## Honest limits

- **Not spec conformance.** See the correction above. An implementation failing these is not
  violating the Falcon spec; it is falling below the premise the security proof rests on.
- **Tested against one reference lineage.** Expected values come from PQClean falcon-512 `clean`.
  Cross-checks against other independent implementations are welcome and are the obvious next step.
- **The degradation model is synthetic.** "Coarse" is simulated by clearing (or rounding up) the low
  bits of the reference result, which isolates precision as the only variable. A real coarse
  polynomial differs in other ways too, and may err in a different direction at different `x`.
- **A passing result is not a proof of correctness.** These vectors detect precision below 2⁻⁴⁰ at
  the points they sample. They say nothing about the rest of your sampler.

## Credit

Requested by [@aszepieniec](https://github.com/aszepieniec) in the `falcon-rust` advisory thread, who
asked for something universal rather than repo-specific, and who supplied the spec-versus-refinement
correction that frames this document.

Analysis and vector construction: Conner Webber, with AI assistance (Anthropic Claude/Opus). Every
quantitative claim here is produced by a program in `tools/` that compiles and runs against PQClean's
reference implementation, and is reproducible from this repository.

[Prest'17]: https://eprint.iacr.org/2017/480
[Howe–Prest–Ricosset–Rossi'19]: https://eprint.iacr.org/2019/1411
