# Building and regenerating

Everything here runs against a PQClean checkout. Nothing is vendored, so the reference stays
identifiably upstream rather than a copy that could drift.

## Prerequisites

- `gcc` (tested with 13.3)
- Python 3.9+
- A PQClean checkout. The paths below assume it sits at `../../scratch_sweep/pqclean`; adjust `F` and
  `C` if yours is elsewhere.

## Build

Three binaries: the reference, and two degraded builds that simulate a coarse `exp()` erring in each
direction.

```sh
F=../../scratch_sweep/pqclean/crypto_sign/falcon-512/clean
C=../../scratch_sweep/pqclean/common
SRC="$F/fpr.c $F/common.c $F/rng.c $F/codec.c $F/fft.c $F/keygen.c $F/vrfy.c \
     $C/fips202.c $C/randombytes.c"

gcc -O2                            -I$F -I$C -o kat_harness         kat_harness.c $SRC
gcc -O2 -DDEGRADE_BITS=30          -I$F -I$C -o kat_harness_deg_down kat_harness.c $SRC
gcc -O2 -DDEGRADE_BITS=30 -DDEGRADE_UP -I$F -I$C -o kat_harness_deg_up   kat_harness.c $SRC

# and two builds that are COARSE BUT STILL INSIDE THE BAR (~2^-45), the positive control
gcc -O2 -DDEGRADE_BITS=18              -I$F -I$C -o kat_harness_good_dn  kat_harness.c $SRC
gcc -O2 -DDEGRADE_BITS=18 -DDEGRADE_UP -I$F -I$C -o kat_harness_good_up  kat_harness.c $SRC
```

The last two matter more than they look. A two-armed test -- reference versus a 2^-33 build -- passes
identically whether the vectors discriminate at 2^-40 or at ONE ULP, so it cannot tell "meets the bar"
from "is bit-identical to PQClean". Only an implementation comfortably inside the bar separates those,
and it must AGREE.

`sign.c` is deliberately **absent** from `$SRC` — `kat_harness.c` `#include`s it, because `BerExp`
is `static` and reaching the real one is the entire point. Compiling it separately as well would be a
duplicate-symbol error, and that is the intended guard rail.

## Regenerate the vectors

```sh
python3 gen_vectors.py      # writes ../vectors/berexp.json
```

Each candidate is run through the reference before it is written out; a vector whose reference answer
does not match the construction is raised, never published.

## Verify them

```sh
python3 verify_vectors.py       # reference vs ~2^-33
python3 verify_vectors.py 26    # a milder degradation, ~2^-37
```

Exit 0 only if every vector produces the published answer on the reference **and** the opposite
answer on the degradation that can exercise it. Accept-direction vectors are checked against the
under-computing build, reject-direction against the over-computing one — checking both against a
single direction certifies half the set as useless, which is what the first version of this script
did.

## Harness verbs

```
kat_harness expm    <r> <ccs>                            -> fpr_expm_p63, as u64
kat_harness berexp  <x> <ccs> <hexbytes>                 -> accept/reject, and the z compared
kat_harness sampler <mu> <sigma> <sigma_min> <hexbytes>  -> sampled z
kat_harness gauss0  <hexbytes>                           -> z0, and the bytes as consumed
```

`gauss0` exists to make the portability problem visible: it prints the `u64` exactly as
`gaussian0_sampler` reads it (little-endian) alongside the resulting `z0`. Point it at the same byte
stream in two implementations and any difference in byte-consumption convention shows up immediately
— which is why full `sampler_z` vectors are not published as universal.

`fpr` is the IEEE-754 binary64 bit pattern in a `uint64_t` (verified: `fpr_log2` ==
`0x3FE62E42FEFA39EF`), so doubles convert by `memcpy`.
