# Testing

**Testing your own implementation?** This file is not it. This is about whether *this repository* is
trustworthy — how the vectors are generated, and how that generation is checked. For wiring
`berexp.json` into your project's test suite, see **Wiring them into your own test suite** in
`README.md`.

```sh
cd tools
python3 selftest.py       # exit 0 if everything holds
```

One command decides whether this repository is trustworthy right now. It builds nothing — see
`tools/README.md` for the five `gcc` lines first — but it checks everything else, including whether
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
| **1** build products | all five harnesses exist, vectors file present | running the suite against a stale or missing build and reading the result as a pass |
| **2** reference arithmetic | `expm(0, ccs) == ccs·2⁶³`; `expm` strictly decreasing in `r`; linear in `ccs` | an off-by-a-power-of-two in the `fpr` conversion, swapped arguments, or a `memcpy` that reads the wrong end of the double — none of which the vectors alone would reveal |
| **3** degradation is live | down-build under-computes, up-build over-computes, relative error measures ≈2⁻³³ | the single worst failure available here: a degradation that does nothing, which makes every vector "discriminate" vacuously because both builds agree by accident |
| **4** vectors vs reference | 20 present, 10 in each error direction, no duplicate byte streams, every published answer reproduced | a hand-edited vector, a regeneration that silently dropped one direction, copy-paste duplicates |
| **5** discrimination | all 20 flip against the degradation that can exercise them | a vector whose drawn value drifted outside the window and no longer tests anything |
| **6** tautology guard | an inverted expected answer is rejected; a byte stream moved far outside the window does **not** discriminate | the suite passing because it cannot fail |

**Stage 5b is why the two-armed version was not enough.** Reference-versus-2⁻³³ passes identically
whether a vector discriminates at the bar or at a single ULP — the harness is blind to the difference
by construction. Only an implementation *inside* the bar tells them apart, by agreeing.

Measured across all 20 vectors in both directions. An earlier version of this paragraph quoted the
single most flattering vector and called it "measured"; these are the full ranges:

| quantity | measured |
|---|---|
| relative error the positive-control build actually reaches | **2⁻⁴³·⁸⁰** (nominal label 2⁻⁴⁵) |
| relative error the degraded build actually reaches | **2⁻³¹·⁶⁸** (nominal label 2⁻³³) |
| discrimination window \|z − u\| | 2²²·⁵⁷ – 2²³·⁴⁶ |
| displacement caused by the positive control | up to 2¹⁸·⁹² |
| margin (window ÷ displacement) | **13.9× at the tightest vector, 338.1× at the loosest** |
| agreement of the positive control | 40/40 |

The nominal labels follow the repo's `63 − DEGRADE_BITS` convention and run ~1.3 bits optimistic,
because `fpr_expm_p63` returns `ccs·exp(−r)·2⁶³`, which measures **0.37–0.69 × 2⁶³** over these
inputs rather than a full 2⁶³. Quote the measured column.

**The two shifts are not the same number, and should not be.** 33 − 31.68 = 1.32 and
45 − 43.80 = 1.20, so the measured figures differ by 12.12 bits rather than the 12.00 the nominal
labels differ by. That is expected, not an inconsistency: clearing *n* low bits removes whatever
those bits happened to be, not exactly 2ⁿ — measured, the removed amount ranges 0.11–1.89 × 2ⁿ
across the set — and the worst case is attained at a *different vector* for each build
(Falcon-512 x=0.65 for the positive control, Falcon-1024 x=0.65 for the degraded one). A gap of
exactly 12.00 would be the surprising result, since it would require the errors to be exactly 2ⁿ at
the same vector.

(That range is the function's *own* output. An earlier version of this sentence gave 0.74–1.37,
which is the range of `z` — the BerExp comparison value, exactly 2× larger — and it was impossible
against the table directly above it: a 0.74 floor caps a 30-bit clearing at 2⁻³²·⁵⁷, while the table
measures 2⁻³¹·⁶⁸. The 0.37 floor gives 2⁻³¹·⁵⁷, which the measurement sits just inside. It is also
ruled out on the domain alone: `ccs < 1` and `exp(−r) ≤ 1`, so the function cannot reach 1.37 × 2⁶³
on any legal input — see the `ccs < 1` trap below.)

Note what this does **not** establish. It does not show the vectors discriminate exactly at some
particular bar. It shows that a build reaching 2⁻⁴³·⁸ — just inside HPRR'19's derived 2⁻⁴³ figure for
Falcon, see the precision note in the README — still agrees on every vector, while one at 2⁻³¹·⁷ does
not. It also softens the "one reference lineage" limitation below: an implementation that agrees here
is doing more than bit-matching PQClean.

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

- **Other implementations.** Everything is checked against PQClean falcon-512 `clean`. An earlier
  version of this line called "a second independent lineage agreeing" the obvious next step. That was
  checked and the step does not exist: falcon-rust and `pornin/rust-fn-dsa` are separately written
  codebases whose `exp` coefficients are **byte-identical** to PQClean's, all citing ePrint 2018/1234.
  Additional implementations add substrates, not independence. See `cross-check/README.md`.
- **Realistic coarse arithmetic.** "Coarse" is simulated by clearing or rounding up the low bits of
  the reference result, which isolates precision as the only variable. A real under-provisioned
  polynomial differs in other ways and may err in different directions at different `x`. The vectors
  cover both directions for that reason, but the model is still synthetic.
- **The `sampler_z` portability claim.** The `z = 101` measurement in `README.md` is a fact about
  PQClean and a report of falcon-rust's published values; it is not re-verified here against
  falcon-rust directly.
- **Whether 2⁻⁴⁰ is the right threshold.** It is the window these vectors are *built at*, not a
  figure from either paper — HPRR'19 derives ~2⁻⁴³ for Falcon and Prest'17 gives δ ≤ 2⁻³⁷ for
  λ ≤ 256. Since 2⁻⁴³ is stricter, an implementation between 2⁻⁴⁰ and 2⁻⁴³ passes here while sitting
  under the derived requirement. The vectors test against 2⁻⁴⁰; they do not justify it, and they do
  not reach 2⁻⁴³. See the precision section of `README.md`.

## Regenerating

```sh
python3 gen_vectors.py     # rewrites ../vectors/berexp.json
python3 selftest.py        # must still pass afterwards
```

`gen_vectors.py` confirms each candidate on the reference before writing it out and raises rather than
publishing a vector the reference disagrees with. Regeneration is deterministic: the same PQClean
checkout produces the same file.
