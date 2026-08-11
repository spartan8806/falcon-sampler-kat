# Testing

```sh
cd tools
python3 selftest.py       # exit 0 if everything holds
```

One command decides whether this repository is trustworthy right now. It builds nothing — see
`tools/README.md` for the three `gcc` lines first — but it checks everything else, including whether
the checking itself is capable of failing.

## Why there are two scripts

`verify_vectors.py` answers one question: *do the published vectors discriminate?* That is necessary
and not sufficient. It assumes the harness computes the right thing and that the degraded build is
genuinely degraded. If the harness were subtly wrong, or the `-DDEGRADE_BITS` build silently inert,
`verify_vectors.py` would still print a clean `20/20` — every number would just be wrong together, in
agreement.

`selftest.py` checks the chain underneath the vectors, then tries to break its own conclusion.

## What each stage would catch

| stage | checks | would catch |
|---|---|---|
| **1** build products | all three harnesses exist, vectors file present | running the suite against a stale or missing build and reading the result as a pass |
| **2** reference arithmetic | `expm(0, ccs) == ccs·2⁶³`; `expm` strictly decreasing in `r`; linear in `ccs` | an off-by-a-power-of-two in the `fpr` conversion, swapped arguments, or a `memcpy` that reads the wrong end of the double — none of which the vectors alone would reveal |
| **3** degradation is live | down-build under-computes, up-build over-computes, relative error measures ≈2⁻³³ | the single worst failure available here: a degradation that does nothing, which makes every vector "discriminate" vacuously because both builds agree by accident |
| **4** vectors vs reference | 20 present, 10 in each error direction, no duplicate byte streams, every published answer reproduced | a hand-edited vector, a regeneration that silently dropped one direction, copy-paste duplicates |
| **5** discrimination | all 20 flip against the degradation that can exercise them | a vector whose drawn value drifted outside the window and no longer tests anything |
| **6** tautology guard | an inverted expected answer is rejected; a byte stream moved far outside the window does **not** discriminate | the suite passing because it cannot fail |

**Stage 5b is why the two-armed version was not enough.** Reference-versus-2⁻³³ passes identically
whether a vector discriminates at 2⁻⁴⁰ or at a single ULP — the harness is blind to the difference by
construction. Only an implementation *inside* the bar tells them apart, by agreeing. Measured: a
2⁻⁴⁵ build moves the computed value by ~2¹⁵ against a window of ~2²², about 155× inside, and agrees on
40/40 checks. That also softens the "one reference lineage" limitation below, since any implementation
within 2⁻⁴⁰ now provably agrees regardless of lineage.

Stage 6 is the one worth arguing about. Stages 1–5 all passing means little on its own: a check that
cannot fail proves nothing about what it claims to check. So the last stage inverts a published answer
and confirms the reference disagrees, then moves a drawn value a long way out of the discrimination
window and confirms the two builds then **agree** — proving the flips in stage 5 come from the window
placement and not from the degradation shifting everything regardless of input.

## A domain trap, recorded because it bit on the first run

`fpr_expm_p63` requires **`ccs < 1`**. In a real sampler `ccs = σ_min/σ` and `σ > σ_min` always, so
`ccs == 1.0` is outside the function's contract and overflows to `0`.

The first version of stage 2 anchored on `expm(0, 1.0) == 2⁶³` and reported three failures against a
perfectly correct harness. The test was wrong, not the code. Every check now uses a `ccs` a real
sampler would actually produce, and the reason is written into the script so it does not get
re-introduced.

This is also the reason stage 2 exists at all: without it, that class of mistake lives in the harness
instead of the test, and the vectors inherit it silently.

## What this does not cover

- **Other implementations.** Everything is checked against PQClean falcon-512 `clean`. A second
  independent lineage agreeing would be worth more than any check here, and is the obvious next step.
- **Realistic coarse arithmetic.** "Coarse" is simulated by clearing or rounding up the low bits of
  the reference result, which isolates precision as the only variable. A real under-provisioned
  polynomial differs in other ways and may err in different directions at different `x`. The vectors
  cover both directions for that reason, but the model is still synthetic.
- **The `sampler_z` portability claim.** The `z = 101` measurement in `README.md` is a fact about
  PQClean and a report of falcon-rust's published values; it is not re-verified here against
  falcon-rust directly.
- **Whether 2⁻⁴⁰ is the right threshold.** That comes from Prest'17 and HPRR'19, not from anything in
  this repository. The vectors test against that number; they do not justify it.

## Regenerating

```sh
python3 gen_vectors.py     # rewrites ../vectors/berexp.json
python3 selftest.py        # must still pass afterwards
```

`gen_vectors.py` confirms each candidate on the reference before writing it out and raises rather than
publishing a vector the reference disagrees with. Regeneration is deterministic: the same PQClean
checkout produces the same file.
