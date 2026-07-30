/*
 * nucula_wallet_stub.c — host stub implementations for nucula wallet.
 *
 * The real nucula_wallet requires libsecp256k1 + HTTP client + NVS.
 * For host unit tests we provide no-op implementations so tollgate_balloon.c
 * compiles and links without the ESP-IDF wallet stack.
 */
#include "nucula_wallet.h"

esp_err_t nucula_wallet_init(const char *mint_url)
{
    (void)mint_url;
    return ESP_OK;
}

esp_err_t nucula_wallet_receive(const char *token_str)
{
    (void)token_str;
    return ESP_OK;
}

esp_err_t nucula_wallet_send(uint64_t amount_sat, char *token_out,
                              size_t token_out_size)
{
    (void)amount_sat;
    if (token_out && token_out_size > 0) token_out[0] = '\0';
    return ESP_OK;
}

uint64_t nucula_wallet_balance(void) { return 0; }
int      nucula_wallet_proof_count(void) { return 0; }
char    *nucula_wallet_proofs_json(void) { return NULL; }
esp_err_t nucula_wallet_swap_all(void) { return ESP_OK; }
esp_err_t nucula_wallet_melt(const char *bolt11, uint64_t max_fee)
{
    (void)bolt11; (void)max_fee;
    return ESP_OK;
}
void nucula_wallet_print_status(void) {}
