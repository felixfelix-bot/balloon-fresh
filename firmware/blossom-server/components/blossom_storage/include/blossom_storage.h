#ifndef BLOSSOM_STORAGE_H
#define BLOSSOM_STORAGE_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include "esp_err.h"

/**
 * Mount LittleFS at /blossom on the "blossom" partition.
 * Formats the filesystem on first boot if needed.
 * Must be called once before any other blossom_storage function.
 *
 * @return ESP_OK on success.
 */
esp_err_t blossom_storage_init(void);

/**
 * Store a blob and its metadata sidecar on LittleFS.
 *
 * @param sha256_hex   NUL-terminated 64-char lowercase hex SHA-256 hash (blob name).
 * @param data         Pointer to raw blob bytes.
 * @param len          Length of blob in bytes.
 * @param content_type NUL-terminated MIME type string (e.g. "image/png").
 *                     May be NULL — defaults to "application/octet-stream".
 *
 * @return ESP_OK on success, error otherwise.
 */
esp_err_t blossom_storage_store(const char *sha256_hex,
                                const uint8_t *data, size_t len,
                                const char *content_type);

/**
 * Fill `out` with the LittleFS path for a given blob, e.g. "/blossom/<sha256>".
 *
 * @param sha256_hex  64-char hex hash.
 * @param out         Output buffer.
 * @param out_len     Size of output buffer (must be >= 64 + 10 bytes).
 * @return ESP_OK on success.
 */
esp_err_t blossom_storage_get_path(const char *sha256_hex,
                                   char *out, size_t out_len);

/**
 * Check whether a blob file exists on the filesystem.
 *
 * @param sha256_hex 64-char hex hash.
 * @return true if the blob file exists, false otherwise.
 */
bool blossom_storage_exists(const char *sha256_hex);

/**
 * Get the size of a stored blob in bytes.
 *
 * @param sha256_hex 64-char hex hash.
 * @return File size in bytes, or 0 if not found / error.
 */
size_t blossom_storage_get_size(const char *sha256_hex);

/**
 * Read the MIME type from the .meta sidecar for a blob.
 *
 * @param sha256_hex 64-char hex hash.
 * @param out        Output buffer for MIME string.
 * @param out_len    Size of output buffer.
 * @return ESP_OK on success, ESP_ERR_NOT_FOUND if blob has no metadata.
 */
esp_err_t blossom_storage_get_type(const char *sha256_hex,
                                   char *out, size_t out_len);

/**
 * Delete a blob file and its .meta sidecar.
 *
 * @param sha256_hex 64-char hex hash.
 * @return ESP_OK on success.
 */
esp_err_t blossom_storage_delete(const char *sha256_hex);

/**
 * List all stored blobs as a JSON array string.
 * (Optional — for future BUD list endpoint.)
 *
 * @param out_json Output buffer for JSON string.
 * @param out_len  Size of output buffer.
 * @return ESP_OK on success.
 */
esp_err_t blossom_storage_list(char *out_json, size_t out_len);

#endif /* BLOSSOM_STORAGE_H */
