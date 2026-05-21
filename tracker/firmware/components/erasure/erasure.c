#include "erasure.h"
#include <string.h>

static int32_t prbs23(int32_t value)
{
    int32_t b0 = value & 0x01;
    int32_t b1 = (value & 0x20) >> 5;
    return (value >> 1) + ((b0 ^ b1) << 22);
}

static void get_parity_matrix_row(int32_t n, int32_t m, uint8_t *matrix_row)
{
    int32_t m_temp = 0;
    if ((m & (m - 1)) == 0) {
        m_temp = 1;
    }

    int32_t x = 1 + (1001 * n);
    int32_t row_size = (m >> 3) + 1;

    memset(matrix_row, 0, row_size);

    int32_t nb_coeff = 0;
    while (nb_coeff < (m >> 1)) {
        int32_t r = 1 << 16;
        while (r >= m) {
            x = prbs23(x);
            r = x % (m + m_temp);
        }
        matrix_row[r >> 3] |= (1 << (r & 7));
        nb_coeff++;
    }
}

static inline int get_parity(int32_t index, const uint8_t *matrix_row)
{
    return (matrix_row[index >> 3] >> (index & 7)) & 1;
}

static void xor_line(uint8_t *dst, const uint8_t *src, uint16_t size)
{
    for (uint16_t i = 0; i < size; i++) {
        dst[i] ^= src[i];
    }
}

static int32_t find_missing_index(erasure_decoder_t *dec, uint16_t frag_index)
{
    for (int32_t i = 0; i < dec->frag_nb; i++) {
        if (dec->frag_nb_missing[i] == frag_index) {
            return i;
        }
    }
    return -1;
}

static void mark_received(erasure_decoder_t *dec, uint16_t frag_index)
{
    for (int32_t i = 0; i < dec->frag_nb; i++) {
        if (dec->frag_nb_missing[i] == frag_index) {
            dec->frag_nb_missing[i] = 0xFFFF;
            dec->frag_nb_lost--;
            return;
        }
    }
}

static void ge_solve(erasure_decoder_t *dec)
{
    int32_t missing_indices[ERASURE_MAX_FRAGS];
    int32_t num_missing = 0;

    for (int32_t i = 0; i < dec->frag_nb; i++) {
        if (dec->frag_nb_missing[i] != 0xFFFF) {
            missing_indices[num_missing++] = i;
        }
    }

    if (num_missing == 0) {
        dec->complete = true;
        return;
    }

    if (dec->m2b_rows < (uint16_t)num_missing) {
        return;
    }

    int32_t n = num_missing;
    int32_t row_bytes = (n + 7) / 8;

    uint8_t A[ERASURE_MAX_FRAGS * ERASURE_MAX_FRAGS / 8];
    uint8_t B[ERASURE_MAX_FRAGS * ERASURE_MAX_FRAG_SIZE];

    memset(A, 0, (uint32_t)n * row_bytes);
    memset(B, 0, (uint32_t)n * dec->frag_size);

    int32_t valid_rows = 0;
    for (int32_t row = 0; row < dec->m2b_rows && valid_rows < n; row++) {
        uint8_t *src = dec->matrix_m2b + (uint32_t)row * ((dec->frag_nb >> 3) + 1);
        uint8_t *dst_row = A + (uint32_t)valid_rows * row_bytes;
        uint8_t *src_data = dec->assembly_buf + (uint32_t)dec->frag_nb * dec->frag_size + (uint32_t)row * dec->frag_size;

        for (int32_t col = 0; col < n; col++) {
            if (get_parity(missing_indices[col], src)) {
                dst_row[col >> 3] |= (1 << (col & 7));
            }
        }

        int32_t bits_set = 0;
        for (int32_t b = 0; b < row_bytes; b++) bits_set += __builtin_popcount(dst_row[b]);
        if (bits_set == 0) continue;

        memcpy(B + (uint32_t)valid_rows * dec->frag_size, src_data, dec->frag_size);
        valid_rows++;
    }

    if (valid_rows < n) return;

    for (int32_t pivot = 0; pivot < n; pivot++) {
        uint8_t *prow = A + (uint32_t)pivot * row_bytes;
        if (!get_parity(pivot, prow)) {
            for (int32_t swap = pivot + 1; swap < n; swap++) {
                uint8_t *srow = A + (uint32_t)swap * row_bytes;
                if (get_parity(pivot, srow)) {
                    uint8_t tmp[ERASURE_MAX_FRAGS / 8];
                    memcpy(tmp, prow, row_bytes);
                    memcpy(prow, srow, row_bytes);
                    memcpy(srow, tmp, row_bytes);

                    uint8_t tdata[ERASURE_MAX_FRAG_SIZE];
                    uint8_t *pd = B + (uint32_t)pivot * dec->frag_size;
                    uint8_t *sd = B + (uint32_t)swap * dec->frag_size;
                    memcpy(tdata, pd, dec->frag_size);
                    memcpy(pd, sd, dec->frag_size);
                    memcpy(sd, tdata, dec->frag_size);
                    break;
                }
            }
        }

        if (!get_parity(pivot, prow)) return;

        for (int32_t elim = 0; elim < n; elim++) {
            if (elim == pivot) continue;
            uint8_t *erow = A + (uint32_t)elim * row_bytes;
            if (get_parity(pivot, erow)) {
                for (int32_t b = 0; b < row_bytes; b++) erow[b] ^= prow[b];
                xor_line(B + (uint32_t)elim * dec->frag_size,
                         B + (uint32_t)pivot * dec->frag_size,
                         dec->frag_size);
            }
        }
    }

    for (int32_t i = 0; i < n; i++) {
        uint32_t offset = (uint32_t)missing_indices[i] * dec->frag_size;
        memcpy(dec->assembly_buf + offset, B + (uint32_t)i * dec->frag_size, dec->frag_size);
        mark_received(dec, missing_indices[i]);
    }

    if (dec->frag_nb_lost == 0) {
        dec->complete = true;
    }
}

void erasure_decoder_init(erasure_decoder_t *dec, uint16_t frag_nb, uint8_t frag_size,
                          uint8_t *assembly_buf, uint8_t *matrix_buf)
{
    memset(dec, 0, sizeof(*dec));
    dec->frag_nb = frag_nb;
    dec->frag_size = frag_size;
    dec->assembly_buf = assembly_buf;
    dec->matrix_m2b = matrix_buf;
    dec->frag_nb_lost = frag_nb;

    for (uint16_t i = 0; i < frag_nb; i++) {
        dec->frag_nb_missing[i] = i;
    }
    memset(assembly_buf, 0, (uint32_t)frag_nb * frag_size);
    memset(matrix_buf, 0, (uint32_t)((ERASURE_MAX_REDUNDANCY >> 3) + 1) * ERASURE_MAX_REDUNDANCY);
}

int erasure_decoder_process(erasure_decoder_t *dec, uint16_t frag_counter, const uint8_t *raw_data)
{
    if (dec->complete) {
        return 0;
    }

    if (frag_counter == 0 || frag_counter > dec->frag_nb + ERASURE_MAX_REDUNDANCY) {
        return -1;
    }

    if (frag_counter <= dec->frag_nb) {
        uint32_t offset = (uint32_t)(frag_counter - 1) * dec->frag_size;
        memcpy(dec->assembly_buf + offset, raw_data, dec->frag_size);
        mark_received(dec, frag_counter - 1);

        if (dec->frag_nb_lost == 0) {
            dec->complete = true;
            return 0;
        }
        dec->frags_received++;
        return 1;
    }

    uint16_t redundancy_idx = frag_counter - dec->frag_nb;

    uint8_t matrix_row[(ERASURE_MAX_FRAGS >> 3) + 1];
    get_parity_matrix_row(redundancy_idx, dec->frag_nb, matrix_row);

    uint8_t temp_data[ERASURE_MAX_FRAG_SIZE];
    memcpy(temp_data, raw_data, dec->frag_size);

    for (int32_t i = 0; i < dec->frag_nb; i++) {
        if (get_parity(i, matrix_row)) {
            if (find_missing_index(dec, i) < 0) {
                uint32_t offset = (uint32_t)i * dec->frag_size;
                xor_line(temp_data, dec->assembly_buf + offset, dec->frag_size);
            }
        }
    }

    uint16_t num_in_row = 0;
    for (int32_t i = 0; i < dec->frag_nb; i++) {
        if (get_parity(i, matrix_row) && find_missing_index(dec, i) >= 0) {
            num_in_row++;
        }
    }

    if (num_in_row == 1) {
        for (int32_t i = 0; i < dec->frag_nb; i++) {
            if (get_parity(i, matrix_row) && find_missing_index(dec, i) >= 0) {
                uint32_t offset = (uint32_t)i * dec->frag_size;
                memcpy(dec->assembly_buf + offset, temp_data, dec->frag_size);
                mark_received(dec, i);
                break;
            }
        }
        if (dec->frag_nb_lost == 0) {
            dec->complete = true;
            return 0;
        }
    } else if (num_in_row > 1) {
        int32_t row_bytes = (dec->frag_nb >> 3) + 1;
        uint8_t *m2b_row = dec->matrix_m2b + (uint32_t)dec->m2b_rows * row_bytes;
        memset(m2b_row, 0, row_bytes);
        for (int32_t i = 0; i < dec->frag_nb; i++) {
            if (get_parity(i, matrix_row) && find_missing_index(dec, i) >= 0) {
                m2b_row[i >> 3] |= (1 << (i & 7));
            }
        }

        uint32_t data_offset = (uint32_t)dec->frag_nb * dec->frag_size + (uint32_t)dec->m2b_rows * dec->frag_size;
        memcpy(dec->assembly_buf + data_offset, temp_data, dec->frag_size);

        dec->m2b_rows++;

        if (dec->m2b_rows >= dec->frag_nb_lost) {
            ge_solve(dec);
            if (dec->complete) return 0;
        }
    }

    dec->frags_received++;

        if (dec->m2b_rows >= 2 && !dec->complete) {
            ge_solve(dec);
            if (dec->complete) return 0;
        }

        for (int32_t retry = 0; retry < dec->m2b_rows && !dec->complete; retry++) {
            uint8_t *row = dec->matrix_m2b + (uint32_t)retry * ((dec->frag_nb >> 3) + 1);
            int32_t only_missing = -1;
            int32_t count = 0;
            for (int32_t i = 0; i < dec->frag_nb; i++) {
                if (get_parity(i, row) && find_missing_index(dec, i) >= 0) {
                    only_missing = i;
                    count++;
                }
            }
            if (count == 1 && only_missing >= 0) {
                uint8_t temp[ERASURE_MAX_FRAG_SIZE];
                uint8_t *src_data = dec->assembly_buf + (uint32_t)dec->frag_nb * dec->frag_size + (uint32_t)retry * dec->frag_size;
                memcpy(temp, src_data, dec->frag_size);
                for (int32_t i = 0; i < dec->frag_nb; i++) {
                    if (get_parity(i, row) && find_missing_index(dec, i) < 0) {
                        xor_line(temp, dec->assembly_buf + (uint32_t)i * dec->frag_size, dec->frag_size);
                    }
                }
                uint32_t offset = (uint32_t)only_missing * dec->frag_size;
                memcpy(dec->assembly_buf + offset, temp, dec->frag_size);
                mark_received(dec, only_missing);
                if (dec->frag_nb_lost == 0) {
                    dec->complete = true;
                    return 0;
                }
            }
        }
    return 1;
}

bool erasure_decoder_is_complete(const erasure_decoder_t *dec)
{
    return dec->complete;
}

void erasure_encoder_init(erasure_encoder_t *enc, uint16_t frag_nb, uint8_t frag_size, uint8_t *data)
{
    enc->frag_nb = frag_nb;
    enc->frag_size = frag_size;
    enc->data = data;
}

void erasure_encode_redundant(const erasure_encoder_t *enc, uint16_t redundancy_index, uint8_t *out)
{
    uint8_t matrix_row[(ERASURE_MAX_FRAGS >> 3) + 1];
    get_parity_matrix_row(redundancy_index + 1, enc->frag_nb, matrix_row);

    memset(out, 0, enc->frag_size);
    for (uint16_t i = 0; i < enc->frag_nb; i++) {
        if (get_parity(i, matrix_row)) {
            xor_line(out, enc->data + (uint32_t)i * enc->frag_size, enc->frag_size);
        }
    }
}
