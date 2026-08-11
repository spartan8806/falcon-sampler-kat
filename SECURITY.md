# Security policy

## What a vulnerability looks like in this repository

There is no service here and no library to link against. The security-relevant failure mode is
narrower and more specific:

**A published vector is wrong.**

If a vector in `vectors/berexp.json` claims an answer a correctly-provisioned implementation does not
produce, then anyone using this set to validate their Falcon sampler gets a failing test on correct
code — or, worse in the other direction, a passing test on a sampler that is genuinely
under-provisioned. Either outcome damages the thing this repository exists to support.

That is what I would most like to hear about, and it is worth reporting privately first even though
nothing here is exploitable in the usual sense.

Also in scope:

- The harness computes an expected value incorrectly (e.g. the `fpr` conversion, the byte injection
  into the PRNG buffer, or the `s`/`r` reduction disagreeing with the reference).
- The degradation model in `verify_vectors.py` fails to exercise a vector it claims to confirm, so a
  vector is published as "verified in both directions" when it is not.
- The portability claim about `gaussian0_sampler` is wrong for some implementation, which would make
  the `BerExp`-only argument in the README unsound.

## How to report

**While this repository is private, GitHub's private vulnerability reporting is not available on it.**
That feature is public-repository only, so the *Security* tab has no *Report a vulnerability* entry —
following the old instruction here would have led to a dead end. Email
**conner.webber000@gmail.com** instead, with `falcon-sampler-kat` in the subject.

If this repository is later made public, private vulnerability reporting will be enabled and becomes
the preferred channel.

For anything that is not a correctness problem — a question, an additional implementation you have
cross-checked against, a request for vectors at a different precision threshold — a public issue is
better, and welcome.

## What you can expect

- Acknowledgement within a few days.
- If a vector is wrong: it is corrected or withdrawn, and the correction is stated plainly in the
  commit and the README rather than quietly amended. A KAT set that silently changes its answers is
  worse than one that never existed, because implementers pin these.
- Credit, unless you would rather not have it.

## What this repository does not claim

Passing these vectors does not mean a Falcon implementation is correct. They detect `exp()` precision
below 2⁻⁴⁰ at the points they sample, and nothing else. The `README.md` "Honest limits" section is
the full statement and is intended to be read as part of this policy.
