/* falcon_kat/kat_harness.c — drive PQClean's REAL Falcon sampler to produce KAT vectors.
 *
 * WHY IT INCLUDES sign.c RATHER THAN REIMPLEMENTING BerExp.
 * The deliverable is a set of vectors described to a maintainer as the list "anyone implementing
 * Falcon must use". If the expected values came from my transcription of BerExp, the document would
 * be asserting that every implementation must agree with MY code. Including sign.c means the numbers
 * come from the reference lineage itself, and a transcription error cannot survive into the vectors.
 * sign.c holds BerExp as `static`, so #include is the only way to reach it.
 *
 * Build (from this directory, in WSL):
 *   F=../../scratch_sweep/pqclean/crypto_sign/falcon-512/clean
 *   gcc -O2 -I$F -o kat_harness kat_harness.c $F/fpr.c $F/common.c $F/rng.c $F/codec.c \
 *       $F/fft.c $F/keygen.c $F/vrfy.c
 *   (sign.c is deliberately NOT on that list — this file includes it.)
 *
 * `fpr` is the IEEE-754 binary64 bit pattern in a uint64_t (verified: fpr_log2 ==
 * 0x3FE62E42FEFA39EF), so a double converts by memcpy.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#include "inner.h"

/* DEGRADED BUILD (-DDEGRADE_BITS=n) — the other half of the proof.
 *
 * A vector that the reference accepts proves only that the reference behaves as constructed. It
 * does NOT prove the vector discriminates. To show that, the identical vector must be run through
 * an implementation whose exp() is under-provisioned, and must come out differently.
 *
 * The degradation is deliberately crude and honest: take the reference's own exp result and clear
 * its low bits, which is exactly a relative error of about 2^-(63-n) with no other behavioural
 * change. That isolates precision as the ONLY variable. A hand-written coarse polynomial would
 * differ in other ways too, and then a flip would not be attributable to precision alone.
 *
 * The macro must be redefined AFTER inner.h (which maps the name to the PQCLEAN_ symbol) and
 * BEFORE sign.c, so that BerExp's own call site picks it up. */
#ifdef DEGRADE_BITS
/* TWO DIRECTIONS, because a coarse approximation is not guaranteed to err low.
 *
 * The first version of this only cleared low bits, i.e. it could only UNDER-compute. Ten of the
 * twenty generated vectors then "failed" to discriminate -- and they were the ten that require an
 * OVER-computing implementation to flip. The vectors were fine; the model of a coarse sampler was
 * one-sided, and a one-sided model silently certifies half a vector set as useless. Build with
 * -DDEGRADE_UP to round up instead. */
static uint64_t degraded_expm(fpr x, fpr ccs) {
    uint64_t v = PQCLEAN_FALCON512_CLEAN_fpr_expm_p63(x, ccs);
    uint64_t low = ((uint64_t)1 << (DEGRADE_BITS)) - 1;
#ifdef DEGRADE_UP
    if (v > UINT64_MAX - low) {
        return UINT64_MAX & ~low;        /* saturate rather than wrap */
    }
    return (v + low) & ~low;
#else
    return v & ~low;
#endif
}
#undef fpr_expm_p63
#define fpr_expm_p63(x, ccs) degraded_expm((x), (ccs))
#endif

#include "sign.c"

static fpr d2f(double d) {
    fpr f;
    memcpy(&f, &d, sizeof f);
    return f;
}

static double f2d(fpr f) {
    double d;
    memcpy(&d, &f, sizeof d);
    return d;
}

/* Load a hex string into the prng buffer and rewind it, so every draw comes from the
 * caller-supplied stream instead of a real RNG. prng_get_u8/prng_get_u64 read straight out of
 * buf.d and only refill past byte 503, so a vector shorter than that is consumed verbatim. */
static int load_bytes(prng *p, const char *hex) {
    size_t n = strlen(hex) / 2, i;
    if (n == 0 || n > 500) {
        return -1;
    }
    memset(p, 0, sizeof *p);
    for (i = 0; i < n; i++) {
        unsigned v;
        if (sscanf(hex + 2 * i, "%2x", &v) != 1) {
            return -1;
        }
        p->buf.d[i] = (uint8_t)v;
    }
    /* Fill the tail with 0xFF: any draw past the supplied vector then reads the LARGEST possible
     * byte, which makes BerExp reject. A vector must never depend on bytes it did not specify, and
     * a deterministic tail makes an accidental dependency show up as a stable wrong answer rather
     * than as noise. */
    memset(p->buf.d + n, 0xFF, sizeof(p->buf.d) - n);
    p->ptr = 0;
    return (int)n;
}

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr,
                "usage:\n"
                "  kat_harness expm <r> <ccs>                     -> fpr_expm_p63, as u64\n"
                "  kat_harness berexp <x> <ccs> <hexbytes>        -> 0/1 and the z it compared\n"
                "  kat_harness sampler <mu> <sigma> <sigma_min> <hexbytes>  -> sampled z\n");
        return 2;
    }

    if (!strcmp(argv[1], "expm") && argc == 4) {
        double r = atof(argv[2]), ccs = atof(argv[3]);
        uint64_t v = fpr_expm_p63(d2f(r), d2f(ccs));
        printf("{\"op\":\"expm\",\"r\":%.17g,\"ccs\":%.17g,"
               "\"expm_p63\":%llu,\"expm_hex\":\"%016llX\"}\n",
               r, ccs, (unsigned long long)v, (unsigned long long)v);
        return 0;
    }

    if (!strcmp(argv[1], "berexp") && argc == 5) {
        double x = atof(argv[2]), ccs = atof(argv[3]);
        prng p;
        int n = load_bytes(&p, argv[4]);
        if (n < 0) {
            fprintf(stderr, "bad hex\n");
            return 2;
        }
        /* Recompute z exactly as BerExp does, so the vector can report the threshold it
         * straddles -- that is the number a reader needs to see WHY the vector discriminates. */
        int s = (int)fpr_trunc(fpr_mul(d2f(x), fpr_inv_log2));
        fpr rr = fpr_sub(d2f(x), fpr_mul(fpr_of(s), fpr_log2));
        uint32_t sw = (uint32_t)s;
        sw ^= (sw ^ 63) & -((63 - sw) >> 31);
        s = (int)sw;
        uint64_t z = ((fpr_expm_p63(rr, d2f(ccs)) << 1) - 1) >> s;

        int b = BerExp(&p, d2f(x), d2f(ccs));
        printf("{\"op\":\"berexp\",\"x\":%.17g,\"ccs\":%.17g,\"s\":%d,\"r\":%.17g,"
               "\"z\":%llu,\"z_hex\":\"%016llX\",\"accept\":%d,\"bytes_used\":%zu}\n",
               x, ccs, s, f2d(rr), (unsigned long long)z, (unsigned long long)z, b, p.ptr);
        return 0;
    }

    /* gaussian0 is where a full-SamplerZ vector stops being portable: it draws 9 bytes
     * (prng_get_u64 LITTLE-endian, then one more byte) and compares against a 72-bit table.
     * An implementation that splits or orders those bytes differently derives a different z0 from
     * the identical stream, so the vector means something else there. This verb makes that visible
     * instead of leaving it as a hypothesis. */
    if (!strcmp(argv[1], "gauss0") && argc == 3) {
        prng p;
        int n = load_bytes(&p, argv[2]);
        if (n < 0) {
            fprintf(stderr, "bad hex\n");
            return 2;
        }
        uint64_t lo = 0;
        int i;
        for (i = 0; i < 8; i++) {
            lo |= (uint64_t)p.buf.d[i] << (8 * i);
        }
        int z0 = PQCLEAN_FALCON512_CLEAN_gaussian0_sampler(&p);
        printf("{\"op\":\"gauss0\",\"z0\":%d,\"bytes_used\":%zu,"
               "\"lo_le\":\"%016llX\",\"hi\":\"%02X\"}\n",
               z0, p.ptr, (unsigned long long)lo, p.buf.d[8]);
        return 0;
    }

    if (!strcmp(argv[1], "sampler") && argc == 6) {
        double mu = atof(argv[2]), sigma = atof(argv[3]), sigma_min = atof(argv[4]);
        sampler_context sc;
        int n = load_bytes(&sc.p, argv[5]);
        if (n < 0) {
            fprintf(stderr, "bad hex\n");
            return 2;
        }
        sc.sigma_min = d2f(sigma_min);
        int z = PQCLEAN_FALCON512_CLEAN_sampler(&sc, d2f(mu), d2f(1.0 / sigma));
        printf("{\"op\":\"sampler\",\"mu\":%.17g,\"sigma\":%.17g,\"sigma_min\":%.17g,"
               "\"z\":%d,\"bytes_used\":%zu}\n",
               mu, sigma, sigma_min, z, sc.p.ptr);
        return 0;
    }

    fprintf(stderr, "bad args\n");
    return 2;
}
