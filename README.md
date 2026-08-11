# Falcon sampler precision KATs

Known-answer test vectors that catch a Falcon implementation whose `exp()` approximation is
under-provisioned — the defect class behind
[GHSA-25rm-9wvm-m38v](https://github.com/aszepieniec/falcon-rust/security/advisories/GHSA-25rm-9wvm-m38v).

**The official Falcon KATs do not catch this.** That is the whole reason these exist. A sampler
running at ~2⁻³³ precision instead of the reference's ~2⁻⁵⁰ still reproduces every published test vector, because the
defect changes `sampler_z`'s output only when the acceptance probability error flips a single
rejection decision — about 2⁻³³ per sample. Catching that with random outputs needs ~2³³ of them, so
no feasible set of end-to-end vectors reliably trips it.

> A note on the advisory's title clause, "reference KAT vectors no longer pass". The vectors
> involved were the crate's own `test_approx_exp` known-answers — ten `(x, ccs, expected)` tuples
> from a sage script citing ePrint 2016/1055 — not the Falcon specification's published KAT set.
> The tolerance on that test went `1u64 << 14` → `1u64 << 40` in `bf2cf00`, the commit that
> introduced `FixedPoint64`, and the reason was written into the source in the same commit:
> "precision introduces ~2³¹ error in the raw z computation (vs ~2¹¹ for f64). We use a loose
> tolerance of 2⁴⁰ to verify the approximation is in the right ballpark while still catching
> catastrophic errors." It is now `1u64 << 23`.
>
> That reads as a documented underestimate of how much error the new container introduced, not as
> anything hidden, and it is the ordinary way this class of defect survives: the tolerance is a
> judgement call made once, by the person least able to see the consequence, and nothing afterwards
> re-examines it. That is the gap these vectors address, and it is general rather than a criticism
> of any crate — a precision defect is invisible to end-to-end sampler outputs, so the only thing
> between it and a green suite is a number somebody chose. A KAT set that fails *because of* the
> precision, at a tolerance nobody has to pick, is the missing piece.

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

The requirement comes from the later analyses — [Prest'17] and [Howe–Prest–Ricosset–Rossi'19] — which
formalised the informal argument in the NIST proposal and identified a relative-precision premise the
security proof needs. Falling below it does not violate the spec; it invalidates the proof's
precondition, so the proof no longer applies.

**The figures, as the papers state them.** An earlier version of this section attributed "~2⁻⁴⁰" to
both papers; neither contains that number. The replacement table then paraphrased *inside* quotation
marks, which was worse — it is corrected here to the papers' own notation and relations.

| source | figure | what the paper actually says |
|---|---|---|
| Prest'17 §3.3 | **2⁻³⁷** | "For λ ≤ 256 and qₛ ≤ 2⁶⁴: … the condition 6 translates to δ ≤ 2⁻³⁷." The symbol is δ, and the bound is for λ **at most** 256 — a higher security level needs a *tighter* δ. |
| HPRR'19 §5 | **2⁻⁴³** | "Then for an implementation of Falcon, the numerical values are 1/**√**(2·(2·λ+1)·Q_exp) **≈** 2⁻⁴³ and 1/(4·Q_bs) ≈ 2⁻⁷⁸", assuming a 256-bit claim. Note the **square root** over the left denominator — only the left one has it. The relation is ≈, not ≤; the paper names no ε₁/ε₂. |
| HPRR'19 §5.1 | **2⁻⁴⁷** | what **P_gal**, *their own* degree-10 GALACTICS polynomial, achieves: "P_gal verifies \|P_gal(x)−exp(x)\|/exp(x) ≤ 2⁻⁴⁷, which is sufficient to verify condition (1) for Falcon implementation." |

Two things worth stating precisely, because it is easy to over-read this table:

- **2⁻⁷⁸ is not a precision.** It is Cond. (2)'s Rényi-divergence slack on the BaseSampler. Only the
  2⁻⁴³ figure is the ApproxExp relative-error condition.
- **2⁻⁴⁷ is not "the reference implementation's precision".** It is HPRR'19's own polynomial.
  PQClean and falcon-rust both evaluate the FACCT polynomial instead, which neither paper measures.
  PQClean documents its own evaluation as within **2⁻⁵⁰**: `fpr.c` states that "tests over more than
  24 billions of random inputs in the 0..log(2) range have never shown a deviation larger than
  2^(-50) from the true mathematical value." That is a bound its authors measured, not one measured
  here.

Two notes on transcribing that middle row, both of which caught out an earlier version of this table:

- **The square root is easy to lose.** Text extraction from the PDF drops the radical glyph, so the
  formula linearises as `1/(2·(2·λ+1)·Q_exp)` — and an earlier version of this table quoted it that
  way. It is self-falsifying at a glance: with λ = 256 and Q_exp ≤ 2⁷⁶ (the paper's Table 1, same
  page), `1/(2·513·2⁷⁶) = 2⁻⁸⁶`, while `1/√(2·513·2⁷⁶) = 2⁻⁴³` — which is what the paper asserts. If
  a quoted formula does not evaluate to its own stated value, the transcription is wrong.
- The paper prints `√(2·(2·λ−1)·Q_exp)` in Cond. (1) and `√(2·(2·λ+1)·Q_exp)` in the §5 sentence
  above. At λ = 256 the difference is immaterial to the 2⁻⁴³ figure.

The Falcon-specific derived figure is therefore **2⁻⁴³**, *stricter* than the 2⁻⁴⁰ this document used
to cite. The consequence for reading these vectors: an implementation between 2⁻⁴⁰ and 2⁻⁴³ is under
the requirement HPRR'19 derives while passing every vector here. See `TESTING.md` for what the
positive control measures (2⁻⁴³·⁸, just inside HPRR'19's figure, agreeing on all 20).

This distinction is due to [@aszepieniec](https://github.com/aszepieniec), who corrected it in the
advisory thread, and it is preserved here deliberately. These vectors test a security-refinement
premise, not spec conformance.

## Using them

`vectors/berexp.json` carries 20 vectors, 10 per parameter set. Each gives `(x, ccs, bytes)` and the
answer a correctly-provisioned implementation must return:

```json
{
  "x": "0.05",
  "ccs": "0.7099076094444444",
  "bytes": "acdf7a6b994c3e32",
  "z_reference": "0xacdf7a6b99f91dad",
  "u_drawn": "0xacdf7a6b994c3e32",
  "reference_accepts": true,
  "discriminates_at": "2^-40",
  "flips_if": "exp() under-computes by more than 2^-40"
}
```

`u_drawn` sits one 2⁻⁴⁰ step from `z_reference`, and that offset IS the window. The two directions are
not symmetric, so check a vector's placement with the matching one:

```
accept vector:  z_reference − u_drawn == ceil(z_reference · 2⁻⁴⁰)        ==  (z >> 40) + 1
reject vector:  u_drawn − z_reference == ceil(z_reference · 2⁻⁴⁰) − 1    ==  (z >> 40)
```

The left-hand identities are what the generator computes, and hold unconditionally. The `(z >> 40)`
forms hold unless `z` is an exact multiple of 2⁴⁰ — at a multiple the offsets are `z >> 40` and
`(z >> 40) − 1` instead — which no published `z` is. (An earlier version of this block wrote the
reject offset as `floor(z_reference · 2⁻⁴⁰)` and hung the exact-multiple caveat on the accept line
only. `ceil − 1` equals that `floor` everywhere *except* at an exact multiple — where the offset
identity on the reject line quietly failed. Note that only that one failed: `floor(z · 2⁻⁴⁰) ==
(z >> 40)` holds at a multiple too, by definition of floor. An earlier version of this sentence said
*both* equalities failed, which is the same overshoot in miniature.)

The `ceil` on the accept side is what guarantees `u < z` strictly, so the reference accepts rather
than landing on the boundary. Measured over the published set: all 10 accept vectors are `(z>>40)+1`,
all 10 reject vectors are exactly `z>>40`. (An earlier version of this line said "exactly `z >> 40`"
in both directions, which is right for half the set.)

Feed `x`, `ccs` and the byte stream to your `BerExp` (or whatever your implementation calls the
Bernoulli-with-probability-exp(−x) step) and compare the accept/reject result. A disagreement on any
vector means your `exp()` is outside 2⁻⁴⁰ in that direction.

**Both error directions are covered.** Ten vectors trip an implementation that under-computes `exp`,
ten trip one that over-computes. This is not hypothetical caution: the real defect in falcon-rust
v0.1.3 errs *over* at `x = 0.05` and *under* at `x = 0.35`, in the same build. A set containing only
one kind would have missed half of them — the same one-sided-test mistake this whole finding is about.

## Why these are `BerExp` vectors and not full `sampler_z` vectors

A full `sampler_z` vector — `(σ_min, μ, σ, bytes) → z` — **is not portable between implementations**,
and this was measured rather than assumed.

Running the `sampler_z` vector from the advisory thread against PQClean's reference returns `z = 101`,
where falcon-rust returns `102` (coarse) / `100` (reference). The cause is not precision at all:
PQClean's `gaussian0_sampler` draws nine bytes as a little-endian `u64` plus one, producing `z0 = 0`
from that stream, where falcon-rust derives `z0 = 1` from the identical bytes.

**Reproducing this, honestly split.** The `z = 101` / `102` / `100` triple came from a vector posted
in the advisory thread; that vector is not published here, so those three numbers are **not**
reproducible from this repository alone — read them as a reported measurement.

The *cause* is, and it is the part that matters. PQClean's `gaussian0_sampler` consumes exactly nine
bytes, low eight little-endian plus one high byte:

```sh
./kat_harness gauss0 0100000000000000ff
{"op":"gauss0","z0":0,"bytes_used":9,"lo_le":"0000000000000001","hi":"FF"}

./kat_harness gauss0 000000000000000000
{"op":"gauss0","z0":18,"bytes_used":9,"lo_le":"0000000000000000","hi":"00"}
```

Nine bytes in, and the low word read little-endian — a different byte-consumption convention over
the same stream lands on a different `z0`, and therefore a different `z`, with arithmetic that is
bit-for-bit correct on both sides. Feed the same hex to your own `gaussian0`/`base_sampler` and
compare `z0` and `bytes_used`; if either differs, a full `sampler_z` vector cannot be shared between
you and PQClean whatever the precision.

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

`tools/verify_vectors.py` re-checks all 20 and refuses to pass if any vector fails either half,
and `tools/selftest.py` checks the whole chain in one command -- including a tautology guard that
confirms the checking is capable of failing. See [TESTING.md](TESTING.md).

## Honest limits

- **Not spec conformance.** See the correction above. An implementation failing these is not
  violating the Falcon spec; it is falling below the premise the security proof rests on.
- **Cross-checked against a second implementation — but not an independent lineage.** Expected values
  come from PQClean falcon-512 `clean`, and all 20 also hold against **falcon-rust v0.3.0**
  (`FixedPoint128`, different language, different container). That is *not* arithmetic independence:
  falcon-rust evaluates the same FACCT polynomial, all 13 coefficients byte-identical, and at all 10
  points v0.3.0 reproduces PQClean's 64-bit `z` exactly. It shows the vectors do not depend on
  PQClean's `fpr` representation; it does not by itself separate the precision bar from bit-identity.
  Against **falcon-rust v0.1.3** — the actual implementation from GHSA-25rm-9wvm-m38v —
  **10 of 20 catch the defect**, every one of the 10 parameter points, since only the vector pointed
  in the implementation's error direction flips at each `x`. That row is the genuinely independent
  one. See [cross-check/](cross-check/). A truly separate lineage would still be worth having.
- **The degradation model in the test suite is synthetic**, though the vectors are not only checked
  against it. "Coarse" is simulated by clearing or rounding up the low bits of the reference result,
  which isolates precision as the only variable. The real defect in falcon-rust v0.1.3 is messier and
  **errs in opposite directions at different `x`** — measured, not assumed, which is exactly why both
  error directions are published. A one-sided set would have missed half of them.
- **A passing result is not a proof of correctness.** These vectors detect precision below 2⁻⁴⁰ at
  the points they sample. They say nothing about the rest of your sampler.
- **The window is 2⁻⁴⁰; HPRR'19's derived figure for Falcon is 2⁻⁴³.** These are not the same
  number, and the vectors use the looser one. An implementation between 2⁻⁴⁰ and 2⁻⁴³ passes every
  vector here while sitting under the precision the analysis derives. Closing that gap means
  regenerating at a `z >> 43` offset, which narrows the window to ~2²⁰ and correspondingly narrows
  the margin measured in `TESTING.md` — worth doing, not yet done. Read a pass as "not
  catastrophically under-provisioned", not as "meets HPRR'19".

## Licence

Apache-2.0 (`LICENSE`) — same as Google's Wycheproof, the closest peer project.

**The vectors themselves are free to copy with no attribution or NOTICE obligation.** The point of
this repository is that implementers paste `(x, ccs, bytes, expected)` into their own test suites, and
a licence question is exactly the kind of friction that stops someone doing that for six numbers.
Apache-2.0 governs the code in `tools/`; consider `vectors/berexp.json` public domain and use it
however is convenient. Attribution is welcome, never required.

No PQClean source is redistributed here. `tools/kat_harness.c` `#include`s `sign.c` from a checkout
you supply, and the linked binaries are not committed. PQClean's Falcon is MIT (Falcon Project,
2017-2019), which is compatible either way.

## Credit

Requested by [@aszepieniec](https://github.com/aszepieniec) in the `falcon-rust` advisory thread, who
asked for something universal rather than repo-specific, and who supplied the spec-versus-refinement
correction that frames this document.

**He has not reviewed these vectors.** His involvement is that request and that correction, nothing
further, and nothing here should be read as his endorsement of the result. Any error in the vectors,
or in the reasoning around them, is mine.

Analysis and vector construction: Conner Webber, with AI assistance (Anthropic Claude/Opus).

**Every *measurement* in this repository is produced by a program in `tools/` that compiles and runs
against PQClean's reference implementation, and is reproducible here.** Figures that are *quoted*
rather than measured are attributed inline where they appear, and are not reproducible from this
repository alone. Those are: the precision figures from Prest'17 and HPRR'19 (read from the papers);
the accuracy of PQClean's FACCT polynomial, quoted as ≤ 2⁻⁵⁰ from its own `fpr.c`, not measured here; the falcon-rust tolerance history and cross-check results (need a falcon-rust
checkout at the named tags — commands in [cross-check/](cross-check/)); and the `z = 101 / 102 / 100`
triple, which came from a vector posted in the advisory thread that is not published here.

An earlier version of this paragraph claimed "two stated exceptions" and named two. There are four.

[Prest'17]: https://eprint.iacr.org/2017/480
[Howe–Prest–Ricosset–Rossi'19]: https://eprint.iacr.org/2019/1411
