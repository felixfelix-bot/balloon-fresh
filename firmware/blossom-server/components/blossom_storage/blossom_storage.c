/*
 * blossom_storage.c — Blob storage over LittleFS for the Blossom server.
 *
 * Each blob is stored as a raw file named by its SHA-256 hex hash on the
 * /blossom LittleFS mount. A JSON sidecar file (<hash>.meta) records the
 * MIME type, size, and upload timestamp.
 *
 * Partitions.csv defines the "blossom" data partition (1.5 MB).
 */
#include "blossom_storage.h"

#include "esp_log.h"
#include "esp_littlefs.h"
#include "esp_timer.h"

#include <stdio.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <dirent.h>
#include <errno.h>

static const char *TAG = "blossom_storage";

/* ── Constants ──────────────────────────────────────────────────── */

#define BLOSSOM_MOUNT      "/blossom"
#define PARTITION_LABEL    "blossom"
#define SHA256_HEX_LEN     64
#define PATH_BUF_LEN       96        /* "/blossom/" + 64 + ".meta" + NUL */

/* ── Internal helpers ───────────────────────────────────────────── */

/**
 * Build the full LittleFS path for a blob.
 * @return true on success, false if buffer too small or bad args.
 */
static bool build_blob_path(const char *sha256_hex, char *out, size_t out_len)
{
    if (!sha256_hex || !out) return false;
    if (out_len < sizeof(BLOSSOM_MOUNT) + 1 + SHA256_HEX_LEN + 1)
        return false;
    snprintf(out, out_len, "%s/%s", BLOSSOM_MOUNT, sha256_hex);
    return true;
}

/**
 * Build the full LittleFS path for a blob's .meta sidecar.
 */
static bool build_meta_path(const char *sha256_hex, char *out, size_t out_len)
{
    if (!sha256_hex || !out) return false;
    if (out_len < sizeof(BLOSSOM_MOUNT) + 1 + SHA256_HEX_LEN + 6)  /* +".meta" + NUL */
        return false;
    snprintf(out, out_len, "%s/%s.meta", BLOSSOM_MOUNT, sha256_hex);
    return true;
}

/* ── Public API ─────────────────────────────────────────────────── */

esp_err_t blossom_storage_init(void)
{
    ESP_LOGI(TAG, "Mounting LittleFS at %s (partition: %s)",
             BLOSSOM_MOUNT, PARTITION_LABEL);

    esp_vfs_littlefs_conf_t conf = {
        .base_path              = BLOSSOM_MOUNT,
        .partition_label        = PARTITION_LABEL,
        .format_if_mount_failed = true,
        .dont_mount             = false,
        .read_only              = false,
    };

    esp_err_t ret = esp_vfs_littlefs_register(&conf);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to mount LittleFS (%s): %s",
                 PARTITION_LABEL, esp_err_to_name(ret));
        return ret;
    }

    size_t total = 0, used = 0;
    if (esp_littlefs_info(PARTITION_LABEL, &total, &used) == ESP_OK) {
        ESP_LOGI(TAG, "LittleFS mounted: %u KB total, %u KB used",
                 (unsigned)(total / 1024), (unsigned)(used / 1024));
    }

    return ESP_OK;
}

esp_err_t blossom_storage_get_path(const char *sha256_hex,
                                   char *out, size_t out_len)
{
    if (!build_blob_path(sha256_hex, out, out_len))
        return ESP_ERR_INVALID_ARG;
    return ESP_OK;
}

bool blossom_storage_exists(const char *sha256_hex)
{
    char path[PATH_BUF_LEN];
    if (!build_blob_path(sha256_hex, path, sizeof(path)))
        return false;
    struct stat st;
    return (stat(path, &st) == 0 && S_ISREG(st.st_mode));
}

size_t blossom_storage_get_size(const char *sha256_hex)
{
    char path[PATH_BUF_LEN];
    if (!build_blob_path(sha256_hex, path, sizeof(path)))
        return 0;
    struct stat st;
    if (stat(path, &st) != 0)
        return 0;
    return (size_t)st.st_size;
}

esp_err_t blossom_storage_store(const char *sha256_hex,
                                const uint8_t *data, size_t len,
                                const char *content_type)
{
    if (!sha256_hex || (!data && len > 0))
        return ESP_ERR_INVALID_ARG;

    char blob_path[PATH_BUF_LEN];
    char meta_path[PATH_BUF_LEN];
    if (!build_blob_path(sha256_hex, blob_path, sizeof(blob_path)) ||
        !build_meta_path(sha256_hex, meta_path, sizeof(meta_path)))
        return ESP_ERR_INVALID_ARG;

    /* Write the blob file */
    int fd = open(blob_path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (fd < 0) {
        ESP_LOGE(TAG, "open(%s) failed: %s", blob_path, strerror(errno));
        return ESP_FAIL;
    }

    size_t written = 0;
    while (written < len) {
        ssize_t n = write(fd, data + written, len - written);
        if (n < 0) {
            ESP_LOGE(TAG, "write(%s) failed: %s", blob_path, strerror(errno));
            close(fd);
            return ESP_FAIL;
        }
        written += (size_t)n;
    }
    close(fd);

    /* Write the .meta sidecar as a small JSON object */
    const char *mime = content_type ? content_type : "application/octet-stream";
    int64_t now_us = esp_timer_get_time();
    int64_t now_s  = now_us / 1000000;

    char meta_json[256];
    int meta_len = snprintf(meta_json, sizeof(meta_json),
                            "{\"size\":%u,\"type\":\"%s\",\"uploaded\":%lld}",
                            (unsigned)len, mime, (long long)now_s);
    if (meta_len < 0 || (size_t)meta_len >= sizeof(meta_json)) {
        ESP_LOGE(TAG, "meta JSON too long for blob %s", sha256_hex);
        return ESP_ERR_NO_MEM;
    }

    int mfd = open(meta_path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
    if (mfd < 0) {
        ESP_LOGE(TAG, "open(%s) failed: %s", meta_path, strerror(errno));
        return ESP_FAIL;
    }
    ssize_t mwritten = write(mfd, meta_json, (size_t)meta_len);
    close(mfd);

    if (mwritten != meta_len) {
        ESP_LOGE(TAG, "Failed to write .meta for %s", sha256_hex);
        return ESP_FAIL;
    }

    ESP_LOGD(TAG, "Stored blob %s (%u bytes, type=%s)",
             sha256_hex, (unsigned)len, mime);
    return ESP_OK;
}

esp_err_t blossom_storage_get_type(const char *sha256_hex,
                                   char *out, size_t out_len)
{
    if (!sha256_hex || !out || out_len == 0)
        return ESP_ERR_INVALID_ARG;

    char meta_path[PATH_BUF_LEN];
    if (!build_meta_path(sha256_hex, meta_path, sizeof(meta_path)))
        return ESP_ERR_INVALID_ARG;

    /* Read the small .meta JSON file */
    int fd = open(meta_path, O_RDONLY);
    if (fd < 0)
        return ESP_ERR_NOT_FOUND;

    char buf[256];
    ssize_t n = read(fd, buf, sizeof(buf) - 1);
    close(fd);
    if (n <= 0)
        return ESP_ERR_NOT_FOUND;
    buf[n] = '\0';

    /* Parse the "type":"..." field (simple string scan — avoids cJSON dep) */
    const char *key = "\"type\":\"";
    const char *p = strstr(buf, key);
    if (!p) {
        strncpy(out, "application/octet-stream", out_len);
        return ESP_OK;
    }
    p += strlen(key);
    const char *end = strchr(p, '"');
    if (!end) {
        strncpy(out, "application/octet-stream", out_len);
        return ESP_OK;
    }

    size_t typelen = (size_t)(end - p);
    if (typelen >= out_len)
        typelen = out_len - 1;
    memcpy(out, p, typelen);
    out[typelen] = '\0';

    return ESP_OK;
}

esp_err_t blossom_storage_delete(const char *sha256_hex)
{
    char blob_path[PATH_BUF_LEN];
    char meta_path[PATH_BUF_LEN];
    if (!build_blob_path(sha256_hex, blob_path, sizeof(blob_path)) ||
        !build_meta_path(sha256_hex, meta_path, sizeof(meta_path)))
        return ESP_ERR_INVALID_ARG;

    esp_err_t ret = ESP_OK;
    if (unlink(blob_path) != 0 && errno != ENOENT) {
        ESP_LOGE(TAG, "unlink(%s) failed: %s", blob_path, strerror(errno));
        ret = ESP_FAIL;
    }
    if (unlink(meta_path) != 0 && errno != ENOENT) {
        ESP_LOGW(TAG, "unlink(%s) failed: %s", meta_path, strerror(errno));
        /* Don't fail if only meta is missing */
    }
    return ret;
}

esp_err_t blossom_storage_list(char *out_json, size_t out_len)
{
    if (!out_json || out_len < 4)
        return ESP_ERR_INVALID_ARG;

    DIR *dir = opendir(BLOSSOM_MOUNT);
    if (!dir) {
        strcpy(out_json, "[]");
        return ESP_OK;
    }

    size_t pos = 0;
    out_json[pos++] = '[';

    struct dirent *ent;
    bool first = true;
    while ((ent = readdir(dir)) != NULL) {
        /* Skip .meta files — only list actual blobs */
        size_t namelen = strlen(ent->d_name);
        if (namelen == SHA256_HEX_LEN && strstr(ent->d_name, ".meta") == NULL) {
            /* Check it's all hex */
            bool valid = true;
            for (size_t i = 0; i < namelen; i++) {
                char c = ent->d_name[i];
                if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') ||
                      (c >= 'A' && c <= 'F'))) {
                    valid = false;
                    break;
                }
            }
            if (!valid) continue;

            const char *sep = first ? "" : ",";
            first = false;

            int w = snprintf(out_json + pos, out_len - pos,
                             "%s\"%.*s\"", sep, (int)namelen, ent->d_name);
            if (w < 0 || (size_t)w >= out_len - pos) {
                /* Buffer full — close the array */
                break;
            }
            pos += (size_t)w;
        }
    }
    closedir(dir);

    if (pos + 1 >= out_len)
        pos = out_len - 2;   /* leave room for ] */
    out_json[pos++] = ']';
    out_json[pos] = '\0';

    return ESP_OK;
}
