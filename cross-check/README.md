# Cross-implementation check

The vectors in `../vectors/berexp.json` were generated against PQClean. On their own that leaves an
obvious question: do they test the **2⁻⁴⁰ precision bar**, or merely **bit-identity with PQClean**?

The only way to answer it is to run them against other implementations. Two matter most: a correct
one that must agree, and the *actual historical defect* that must be caught. `pornin/rust-fn-dsa` was
added afterwards on both its backends.

**Read the agreeing rows with the caveat below them, though** — all of them turn out to share
PQClean's polynomial, so they answer a narrower question than "an independent implementation agrees".
The section after this one is what came of chasing that, and it is the more interesting result.

## Results

| implementation | arithmetic | result |
|---|---|---|
| PQClean falcon-512 `clean` | `uint64_t` software float (`fpr`) | source of the expected answers |
| **falcon-rust v0.3.0** (post-fix) | `FixedPoint128` | **20/20 agree** |
| **falcon-rust v0.1.3** (GHSA-25rm-9wvm-m38v) | `FixedPoint64`, ~2⁻³³ | **10/20 caught the defect** |
| **pornin/rust-fn-dsa v0.4.0** | `flr_native` — hardware `f64` | **20/20 agree**, `z` bit-exact |
| **pornin/rust-fn-dsa v0.4.0** | `flr_emu` — integer IEEE-754 emulation | **20/20 agree**, `z` bit-exact |

**These two are not arithmetically independent, and the distinction matters.** falcon-rust's
`approx_exp` evaluates the *same* FACCT polynomial as PQClean's `fpr_expm_p63`: all 13 coefficients
are byte-identical, in the same order, under the same Horner recurrence `y = C[u] - ((z*y) >> 63)`
and the same final `((expm << 1) - 1) >> s`. Both cite the same source (ePrint 2018/1234 /
`raykzhao/gaussian`). At all 10 points, v0.3.0 does not merely agree on accept/reject — it
reproduces PQClean's 64-bit `z` exactly.

So what this table actually establishes is narrower than "two independent implementations agree",
and worth stating precisely: the vectors are insensitive to PQClean's `fpr` software-float
*representation*, since a different language and a different fixed-point container reach the same
answers. It does **not**, on its own, separate "these vectors test the precision bar" from "these
vectors test bit-identity with PQClean". That separation is made by the positive-control arm of
`tools/selftest.py`, which builds an implementation that is *deliberately different* from PQClean
and comfortably inside the bar, and shows it still agrees 40/40.

The v0.1.3 row above is the independent half, and it is the valuable one: a genuinely different
arithmetic container at ~2⁻³³ is caught.

## Every implementation surveyed evaluates the *same* polynomial

`pornin/rust-fn-dsa` was added to answer "is there a second lineage?", since it is an independently
written codebase rather than a port. It is an independent **implementation** — and it is not an
independent set of **coefficients**, which is the kind that would have answered the question. Those
are different things and the distinction carries the rest of this section.

That prompted a wider survey, 2026-08-17. **Thirteen independently written implementations, eight
languages, three storage conventions — every one evaluates the identical FACCT polynomial** from
ePrint 2018/1234 (`github.com/raykzhao/gaussian`). No independent re-derivation was found.

| implementation | language | stored as |
|---|---|---|
| Falcon round-3 reference / PQClean | C | fixed-point, 13 |
| **`tprest/falcon.py`** (the designers' reference) | Python | fixed-point, 13 |
| `aszepieniec/falcon-rust` | Rust | fixed-point, 13 |
| `pornin/rust-fn-dsa` (native + emulated) | Rust | fixed-point, 13 |
| QRCS-CORP/QSC | C, own AVX2 | fixed-point, 13 |
| wolfSSL | C + x86-64 asm | fixed-point, 13 |
| `itzmeanjan/falcon` | C++20, header-only | fixed-point, 13 |
| `mvojacek/ches-2026-falcon-samplerz` | C (SW side of a HW artifact) | fixed-point, 13 |
| Bouncy Castle | C# | double, 13 |
| Bouncy Castle | Java | double, 13 |
| libpqc-dyber | C | double, 13 |
| `GMUCERG/FALCON_NEON` | C + ARMv8 NEON | double, 13 reversed |
| **`@noble/post-quantum`** | TypeScript | double, **12 + implicit leading 1.0, reversed** |

Vendored copies inherit the lineage rather than evidence it, and are not counted above: liboqs and
`rustpq/pqcrypto` vendor PQClean, `oqs-provider` reaches Falcon through liboqs, and `mupq/pqm4`
carries Pornin's `c-fn-dsa`.

**The origin is not implementers copying each other.** It is in the designers' own reference:
`tprest/falcon.py` carries the coefficients with the comment *"This polynomial is lifted from
FACCT"*. Anyone following the reference inherits it by construction, which is a far more ordinary
explanation than convergence — and a much easier one to check.

```
4741183a3  36548cfc06  24fdcbf140a  171d939de045  d00cf58f6f84  680681cf796e3
2d82d8305b0fea  11111110e066fd0  555555555070f00  155555555581ff00
400000000002b400  7fffffffffff4800  8000000000000000
```

Both Pornin backends reproduce PQClean's 64-bit `z` **exactly** on all 20 vectors, not merely the
accept/reject answer. For `flr_emu` that is by construction and not evidence of independence: it is a
strict IEEE-754 `binary64` emulation in integer arithmetic, so being bit-exact with hardware `f64` is
its job. A different substrate, not a different computation.

**A second finding, which may be the more useful one.** Botan, CIRCL, SymCrypt, mbedTLS, OpenSSL
in-tree, aws-lc, swift-crypto and leancrypto ship ML-KEM and ML-DSA and **do not ship Falcon at
all** — the floating-point Gaussian sampler is why. Every library that did ship it had to write its
own FP layer: wolfSSL (C plus hand-written x86-64 assembly), Bouncy Castle Java (`FPREngine`),
Bouncy Castle C# (`FalconFPR`), QSC (its own AVX2). Four independent FP implementations is four
independent chances at the defect class these vectors are for.

**What that means for these vectors, stated plainly.** They measure whether an implementation
evaluates the agreed polynomial *precisely enough*. They cannot detect a **wrong** polynomial: no
implementation surveyed uses a different one, so none would disagree. If ePrint 2018/1234's
coefficients were themselves subtly wrong, every implementation above — and every vector in this
repository — would be wrong together and perfectly consistent about it.

The defect class these vectors target — a shared polynomial evaluated at inadequate precision — is
exactly the class GHSA-25rm-9wvm-m38v was.

### Scope, and why a grep is not enough

Thirteen is not every implementation. Closed-source, HSM firmware and vendor SDKs were not reachable,
and only the **exp(-x) approximation** was compared — two implementations sharing it can still differ
in rounding, integer widths, comparison logic, control flow, constant-timeness and RNG plumbing.
Nothing here says the FACCT polynomial is wrong; it says nothing surveyed could tell us if it were.

The comparison has to be numeric, because the three storage conventions share no characters and a
text search reports the same polynomial as different lineages. `0x4741183A3 / 2^63` is
`2.0737723659602567e-09`, which is the leading decimal coefficient to within one 2^-63 step — so the
tolerance must be **absolute** and tied to that quantum, not relative: at a coefficient of ~2e-9 the
quantisation is 2.4e-11 in relative terms, which a sane relative tolerance rejects. `@noble` stores
twelve coefficients reversed with the leading `1.0` folded into `return ccs * (1.0 + z * y)`, and
header-only C++ hides in `.hpp`. Each of those three traps produced a false "different lineage"
before it was fixed.

One survey result is deliberately unnamed here: a single personal repository implementing a *Falcon
variant* replaces the polynomial with `std::exp` and seeds its Bernoulli trial from a non-cryptographic
PRNG. It is not a shipped library and naming it would serve nothing.

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
about 2²³, which perturbs the lower-middle bytes — so seven is sufficient.

That is a **measured property of the 20 published vectors** (9 diverge at index 4, 11 at index 5),
not something the generator enforces: `gen_vectors.py` raises on a non-zero harness exit, on
`z == 0`, on `u >= 1<<64` and on an accept/reject mismatch, and has no byte-divergence check. An
earlier version of this paragraph claimed it did.

## Reproducing the Pornin rows

`expm_p63` is `pub(crate)`, so the harness lives inside the crate, same as the falcon-rust case. On
x86_64 the native backend is selected by `cfg`; the emulated one is reached by pointing `mod backend`
at `flr_emu.rs` and building with `--features no_avx2`, since the AVX2 sampler path assumes the
native backend's `to_f64`.

```sh
cargo test --offline -p fn-dsa-sign falcon_sampler_kat -- --nocapture                    # native
cargo test --offline -p fn-dsa-sign --features no_avx2 falcon_sampler_kat -- --nocapture # emu
```

The harness computes `z = ((expm_p63(r, ccs) << 1) - 1) >> s` from each vector's published `r`, `ccs`
and `s`, then compares `u_drawn < z` against `reference_accepts` — the "at the comparison value"
route described in the top-level README, which needs no RNG plumbing.

## What this does not settle

- Three codebases, one polynomial. More implementations would add substrates, not independence — see
  the section above. Contributions of results are still welcome, and a genuinely independent
  polynomial evaluation would be worth more than all of these combined.
- v0.1.3 is one under-provisioned implementation. Another coarse sampler could err differently and be
  caught by a different subset — or, if its error were smaller than 2⁻⁴⁰, not caught here at all.
  Note that "not caught here" is **not** the same as "adequate": HPRR'19 derives ~2⁻⁴³ for Falcon,
  stricter than this window, so an implementation between 2⁻⁴⁰ and 2⁻⁴³ passes every vector while
  sitting under the derived requirement. See *Honest limits* in the top-level README.
- These runs used the vectors as published. They are not a re-derivation of the expected answers from
  `falcon-rust`; PQClean remains the source of the expected values.
