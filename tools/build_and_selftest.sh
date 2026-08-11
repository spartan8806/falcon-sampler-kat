#!/usr/bin/env bash
# Build all five KAT harnesses and run the selftest. Linux/WSL only (gcc + ELF).
#
# Five, not three. The reference plus the two 2^-33 degraded builds prove the vectors DISCRIMINATE;
# the two 2^-45 builds -- coarse but comfortably inside the bar -- prove they discriminate AT THE
# BAR rather than at one ULP. Without the last pair a two-armed test passes identically whether the
# vectors reject "worse than Falcon requires" or merely "not bit-identical to PQClean", and those
# are very different claims to put in an advisory.
set -eu
cd "$(dirname "$0")"

F=${F:-../../scratch_sweep/pqclean/crypto_sign/falcon-512/clean}
C=${C:-../../scratch_sweep/pqclean/common}
[ -d "$F" ] || { echo "no PQClean checkout at $F -- set F= and C="; exit 2; }

SRC="$F/fpr.c $F/common.c $F/rng.c $F/codec.c $F/fft.c $F/keygen.c $F/vrfy.c \
     $C/fips202.c $C/randombytes.c"
# sign.c is deliberately absent: kat_harness.c #includes it, because BerExp is static and reaching
# the real one is the whole point. Listing it here too would be a duplicate-symbol error, which is
# the intended guard rail.

build() { echo "  cc $1"; gcc -O2 "${@:2}" -I"$F" -I"$C" -o "$1" kat_harness.c $SRC; }

echo "building 5 harnesses with $(gcc --version | head -1)"
build kat_harness
build kat_harness_deg_down  -DDEGRADE_BITS=30
build kat_harness_deg_up    -DDEGRADE_BITS=30 -DDEGRADE_UP
build kat_harness_good_dn   -DDEGRADE_BITS=18
build kat_harness_good_up   -DDEGRADE_BITS=18 -DDEGRADE_UP
echo

exec python3 selftest.py "$@"
