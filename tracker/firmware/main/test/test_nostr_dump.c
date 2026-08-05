/*
 * test_nostr_dump.c — Host-side test for the nostr_dump CLI output format.
 *
 * This test verifies that the nostr_store iteration + dump format logic
 * works correctly:
 *   - nostr_store_count() returns the right count
 *   - nostr_store_get() retrieves events in FIFO order
 *   - The dump output format (index, kind, ts, len, pubkey, content) is correct
 *
 * The dump format mirrors cli_cmd_nostr_dump() in app_main.cpp. We don't
 * link against the ESP-IDF CLI here — we test the data path and format.
 *
 * Build & run:
 *   gcc -Wall -Wextra -O2 -I components/nostr_store/include \
 *       -o /tmp/test_nostr_dump main/test/test_nostr_dump.c \
 *       components/nostr_store/nostr_store.c && /tmp/test_nostr_dump
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <sys/stat.h>

#include "nostr_store.h"

#define TEST_DIR "/tmp/nostr_dump_test"

static void clean_test_dir(void)
{
    int rc = system("rm -rf " TEST_DIR);
    (void)rc;
}

static void make_event(nostr_event_t *evt, uint8_t id_byte,
                       uint16_t kind, uint32_t ts, const char *content)
{
    memset(evt, 0, sizeof(*evt));
    /* Unique ID: fill first byte with id_byte, rest with incrementing pattern */
    memset(evt->id, id_byte, NOSTR_EVENT_ID_SIZE);
    memset(evt->pubkey, 0xAA, NOSTR_PUBKEY_SIZE);
    evt->pubkey[0] = id_byte;  /* make pubkey distinguishable */
    evt->created_at = ts;
    evt->kind = kind;
    evt->content_len = (uint16_t)strlen(content);
    memcpy(evt->content, content, evt->content_len);
    evt->num_tags = 0;
}

/*
 * Simulates the dump format from cli_cmd_nostr_dump().
 * Returns a string into `buf` matching the firmware output format.
 */
static void format_dump_line(char *buf, size_t buf_size,
                              uint16_t idx, const nostr_event_t *event)
{
    char content_preview[81];
    uint16_t show_len = event->content_len;
    if (show_len > 80) show_len = 80;
    memcpy(content_preview, event->content, show_len);
    content_preview[show_len] = '\0';

    char pub_hex[17];
    for (int b = 0; b < 8; b++)
        snprintf(pub_hex + b * 2, 3, "%02x", event->pubkey[b]);
    pub_hex[16] = '\0';

    snprintf(buf, buf_size, "[%u] kind=%u ts=%lu len=%u pub=%s %s%s",
             (unsigned)idx,
             (unsigned)event->kind,
             (unsigned long)event->created_at,
             (unsigned)event->content_len,
             pub_hex,
             content_preview,
             event->content_len > 80 ? "..." : "");
}

int main(void)
{
    printf("\n=== Nostr Dump CLI Format Tests ===\n\n");

    /* ---- TEST 1: empty store ---- */
    printf("TEST 1: empty store dump... ");
    clean_test_dir();
    nostr_store_t store;
    nostr_store_init(&store, TEST_DIR);

    uint16_t count = nostr_store_count(&store);
    assert(count == 0);
    /* Firmware prints "Nostr store: 0 events" — we verify the count */
    printf("PASS (count=%u)\n", count);

    /* ---- TEST 2: single event, verify dump format ---- */
    printf("TEST 2: single event dump format... ");
    nostr_event_t evt;
    make_event(&evt, 0x42, 1, 1700000000, "Hello from balloon!");
    int r = nostr_store_add(&store, &evt);
    assert(r == 0);

    count = nostr_store_count(&store);
    assert(count == 1);

    nostr_event_t got;
    r = nostr_store_get(&store, 0, &got);
    assert(r == 0);

    char line[256];
    format_dump_line(line, sizeof(line), 0, &got);
    /* Expected: [0] kind=1 ts=1700000000 len=19 pub=42aaaaaaaaaaaaaa Hello from balloon! */
    printf("\n  %s\n  ", line);

    /* Verify key fields in the formatted line */
    assert(strstr(line, "[0]") != NULL);
    assert(strstr(line, "kind=1") != NULL);
    assert(strstr(line, "ts=1700000000") != NULL);
    assert(strstr(line, "len=19") != NULL);
    assert(strstr(line, "pub=42aaaaaaaaaaaaaa") != NULL);
    assert(strstr(line, "Hello from balloon!") != NULL);
    assert(strstr(line, "...") == NULL);  /* no truncation for short content */
    printf("PASS\n");

    /* ---- TEST 3: multiple events, verify FIFO order ---- */
    printf("TEST 3: multiple events FIFO order... ");
    clean_test_dir();
    nostr_store_init(&store, TEST_DIR);

    const char *contents[] = {"first", "second event", "third", "fourth msg", "fifth!"};
    uint16_t kinds[] = {1, 30023, 4, 1000, 1};
    uint32_t timestamps[] = {100, 200, 300, 400, 500};

    for (int i = 0; i < 5; i++) {
        make_event(&evt, (uint8_t)(i + 1), kinds[i], timestamps[i], contents[i]);
        r = nostr_store_add(&store, &evt);
        assert(r == 0);
    }

    count = nostr_store_count(&store);
    assert(count == 5);

    /* Dump all and verify order */
    printf("\n");
    for (uint16_t i = 0; i < count; i++) {
        r = nostr_store_get(&store, i, &got);
        assert(r == 0);

        format_dump_line(line, sizeof(line), i, &got);
        printf("  %s\n", line);

        /* Verify each event matches what we stored */
        assert(got.kind == kinds[i]);
        assert(got.created_at == timestamps[i]);
        assert(got.content_len == strlen(contents[i]));
        assert(strstr(line, contents[i]) != NULL);

        char expected_kind[16];
        snprintf(expected_kind, sizeof(expected_kind), "kind=%u", (unsigned)kinds[i]);
        assert(strstr(line, expected_kind) != NULL);

        char expected_ts[16];
        snprintf(expected_ts, sizeof(expected_ts), "ts=%u", timestamps[i]);
        assert(strstr(line, expected_ts) != NULL);
    }
    printf("  PASS\n");

    /* ---- TEST 4: content truncation (>80 chars) ---- */
    printf("TEST 4: content truncation... ");
    clean_test_dir();
    nostr_store_init(&store, TEST_DIR);

    /* Create content > 80 chars */
    char long_content[200];
    memset(long_content, 'X', 199);
    long_content[199] = '\0';
    /* 199 chars of 'X' */

    make_event(&evt, 0x99, 1, 1000, long_content);
    r = nostr_store_add(&store, &evt);
    assert(r == 0);

    r = nostr_store_get(&store, 0, &got);
    assert(r == 0);
    assert(got.content_len == 199);

    format_dump_line(line, sizeof(line), 0, &got);
    /* Should have "..." at the end indicating truncation */
    assert(strstr(line, "...") != NULL);
    /* Content portion should be exactly 80 chars */
    /* The format is: ... pub=<16hex> <80chars>... */
    /* Verify the line contains 80 X's before "..." */
    char *content_start = strstr(line, "pub=");
    assert(content_start != NULL);
    content_start += 4 + 16 + 1; /* skip "pub=" + 16 hex + space */
    /* Count consecutive 'X' chars from content_start */
    int xcount = 0;
    while (content_start[xcount] == 'X') xcount++;
    assert(xcount == 80);
    printf("PASS (80 chars shown, %u total, truncated)\n", got.content_len);

    /* ---- TEST 5: pagination (count limit) ---- */
    printf("TEST 5: pagination (limit < count)... ");
    clean_test_dir();
    nostr_store_init(&store, TEST_DIR);

    for (int i = 0; i < 10; i++) {
        char msg[32];
        snprintf(msg, sizeof(msg), "event_%d", i);
        make_event(&evt, (uint8_t)(i + 1), 1, 1000 + i, msg);
        r = nostr_store_add(&store, &evt);
        assert(r == 0);
    }
    count = nostr_store_count(&store);
    assert(count == 10);

    /* Simulate: limit = 3 (user typed "nostr_dump 3") */
    uint16_t limit = 3;
    int dumped = 0;
    for (uint16_t i = 0; i < limit && i < count; i++) {
        r = nostr_store_get(&store, i, &got);
        assert(r == 0);
        dumped++;
    }
    assert(dumped == 3);
    printf("PASS (dumped %d of %u)\n", dumped, count);

    /* ---- TEST 6: non-printable content (sanitization) ---- */
    printf("TEST 6: non-printable content sanitization... ");
    clean_test_dir();
    nostr_store_init(&store, TEST_DIR);

    /* Create content with binary/non-printable chars */
    char bin_content[10];
    bin_content[0] = 'H';
    bin_content[1] = 0x01;   /* non-printable */
    bin_content[2] = 'i';
    bin_content[3] = 0x7F;   /* DEL (non-printable, >0x7E) */
    bin_content[4] = '\0';   /* non-printable */

    make_event(&evt, 0x77, 1, 1000, "test");
    memcpy(evt.content, bin_content, 5);
    evt.content_len = 5;
    r = nostr_store_add(&store, &evt);
    assert(r == 0);

    r = nostr_store_get(&store, 0, &got);
    assert(r == 0);

    /* Simulate the sanitization logic from cli_cmd_nostr_dump */
    char sanitized[81];
    uint16_t show_len = got.content_len;
    if (show_len > 80) show_len = 80;
    memcpy(sanitized, got.content, show_len);
    for (uint16_t c = 0; c < show_len; c++) {
        if (sanitized[c] < 0x20 || sanitized[c] > 0x7E)
            sanitized[c] = '.';
    }
    sanitized[show_len] = '\0';

    /* Verify: H.i. (0x01→'.', 0x7F→'.', 0x00→'.') */
    assert(sanitized[0] == 'H');
    assert(sanitized[1] == '.');
    assert(sanitized[2] == 'i');
    assert(sanitized[3] == '.');
    assert(sanitized[4] == '.');
    printf("PASS (sanitized: \"%s\")\n", sanitized);

    /* ---- cleanup ---- */
    clean_test_dir();

    printf("\n=== Results: 6/6 passed ===\n");
    return 0;
}