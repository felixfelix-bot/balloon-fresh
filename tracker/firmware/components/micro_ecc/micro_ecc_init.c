#include "micro_ecc_platform.h"
#include "uECC.h"

void micro_ecc_init(void) {
    uECC_set_rng(micro_ecc_rng);
}
