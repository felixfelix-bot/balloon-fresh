#include <sdkconfig.h>

#ifdef CONFIG_BENCH_MODE_CONTINUITY

#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_log.h"
#include "driver/gpio.h"

static const char *TAG = "CONT";

#define LED_GPIO 8

struct PinDef {
    const char *name;
    int gpio;
    const char *function;
};

static const PinDef pins[] = {
    {"D0",  0,  "DIO7"},
    {"D1",  1,  "DIO8"},
    {"D2",  2,  "MISO"},
    {"D3",  3,  "RST"},
    {"D4",  4,  "BUSY"},
    {"D5",  5,  "DIO9"},
    {"D6",  6,  "SCK"},
    {"D7",  7,  "MOSI"},
    {"D8",  8,  "LED"},
    {"D9",  9,  "BOOT"},
    {"D10", 10, "NSS"},
};
static const int pin_count = sizeof(pins) / sizeof(pins[0]);

struct PinPair {
    int a_idx;
    int b_idx;
};

static const PinPair pairs[] = {
    {0, 1}, {1, 2}, {2, 3}, {3, 4}, {4, 5},
    {5, 6}, {6, 7}, {7, 8}, {8, 9}, {9, 10},
};
static const int pair_count = sizeof(pairs) / sizeof(pairs[0]);

static void blink(int times, int on_ms, int off_ms) {
    gpio_config_t io = {};
    io.pin_bit_mask = (1ULL << LED_GPIO);
    io.mode = GPIO_MODE_OUTPUT;
    gpio_config(&io);
    for (int i = 0; i < times; i++) {
        gpio_set_level((gpio_num_t)LED_GPIO, 0);
        vTaskDelay(pdMS_TO_TICKS(on_ms));
        gpio_set_level((gpio_num_t)LED_GPIO, 1);
        vTaskDelay(pdMS_TO_TICKS(off_ms));
    }
    gpio_set_level((gpio_num_t)LED_GPIO, 1);
}

static void set_pin_input(int gpio, bool pullup, bool pulldown) {
    gpio_config_t conf = {};
    conf.pin_bit_mask = (1ULL << gpio);
    conf.mode = GPIO_MODE_INPUT;
    conf.pull_up_en = pullup ? GPIO_PULLUP_ENABLE : GPIO_PULLUP_DISABLE;
    conf.pull_down_en = pulldown ? GPIO_PULLDOWN_ENABLE : GPIO_PULLDOWN_DISABLE;
    conf.intr_type = GPIO_INTR_DISABLE;
    gpio_config(&conf);
}

static void set_pin_output(int gpio, int level) {
    gpio_config_t conf = {};
    conf.pin_bit_mask = (1ULL << gpio);
    conf.mode = GPIO_MODE_OUTPUT;
    conf.pull_up_en = GPIO_PULLUP_DISABLE;
    conf.pull_down_en = GPIO_PULLDOWN_DISABLE;
    conf.intr_type = GPIO_INTR_DISABLE;
    gpio_config(&conf);
    gpio_set_level((gpio_num_t)gpio, level);
}

static int read_pin(int gpio) {
    return gpio_get_level((gpio_num_t)gpio);
}

static int test_short_to_gnd(const PinDef *p, bool skip) {
    if (skip) {
        printf("  %-4s (GPIO%-2d, %-5s): SKIP\n", p->name, p->gpio, p->function);
        return -1;
    }
    set_pin_input(p->gpio, true, false);
    vTaskDelay(pdMS_TO_TICKS(2));
    int val = read_pin(p->gpio);

    if (val == 0) {
        printf("  %-4s (GPIO%-2d, %-5s): SHORT TO GND!\n", p->name, p->gpio, p->function);
        return 1;
    }
    printf("  %-4s (GPIO%-2d, %-5s): OK\n", p->name, p->gpio, p->function);
    set_pin_input(p->gpio, false, false);
    return 0;
}

static int test_short_to_vcc(const PinDef *p, bool skip) {
    if (skip) {
        printf("  %-4s (GPIO%-2d, %-5s): SKIP\n", p->name, p->gpio, p->function);
        return -1;
    }
    set_pin_input(p->gpio, false, true);
    vTaskDelay(pdMS_TO_TICKS(2));
    int val = read_pin(p->gpio);

    if (val == 1) {
        printf("  %-4s (GPIO%-2d, %-5s): SHORT TO VCC!\n", p->name, p->gpio, p->function);
        return 1;
    }
    printf("  %-4s (GPIO%-2d, %-5s): OK\n", p->name, p->gpio, p->function);
    set_pin_input(p->gpio, false, false);
    return 0;
}

enum PairResult { PAIR_OK, PAIR_SHORT, PAIR_INCONCLUSIVE };

static PairResult test_pin_pair(const PinDef *a, const PinDef *b) {
    set_pin_input(a->gpio, false, false);
    set_pin_input(b->gpio, true, false);
    vTaskDelay(pdMS_TO_TICKS(2));
    int baseline = read_pin(b->gpio);

    if (baseline == 0) {
        set_pin_input(b->gpio, false, false);
        return PAIR_INCONCLUSIVE;
    }

    set_pin_output(a->gpio, 0);
    vTaskDelay(pdMS_TO_TICKS(2));
    int driven = read_pin(b->gpio);

    set_pin_input(a->gpio, false, false);
    vTaskDelay(pdMS_TO_TICKS(2));
    int released = read_pin(b->gpio);

    set_pin_input(b->gpio, false, false);

    if (driven == 0 && released == 1) {
        return PAIR_SHORT;
    }
    return PAIR_OK;
}

extern "C" void app_main() {
    ESP_LOGI(TAG, "=== Continuity Test ===");
    setvbuf(stdout, NULL, _IONBF, 0);

    blink(3, 200, 200);
    vTaskDelay(pdMS_TO_TICKS(500));

    printf("\n");
    printf("=============================================\n");
    printf("  Continuity / Short-Circuit Test\n");
    printf("  Tests %d pins + %d pin pairs\n", pin_count, pair_count);
    printf("  Radio NOT initialized (pins high-Z)\n");
    printf("=============================================\n");
    printf("\n");
    fflush(stdout);

    int total_shorts = 0;

    printf("--- Phase 1: Signal-to-GND ---\n");
    fflush(stdout);
    for (int i = 0; i < pin_count; i++) {
        bool skip = (pins[i].gpio == LED_GPIO);
        int result = test_short_to_gnd(&pins[i], skip);
        if (result == 1) total_shorts++;
        fflush(stdout);
    }
    printf("\n");

    printf("--- Phase 2: Signal-to-VCC ---\n");
    fflush(stdout);
    for (int i = 0; i < pin_count; i++) {
        bool skip = (pins[i].gpio == LED_GPIO) || (pins[i].gpio == 9);
        int result = test_short_to_vcc(&pins[i], skip);
        if (result == 1) total_shorts++;
        fflush(stdout);
    }
    printf("\n");

    printf("--- Phase 3: Pin-to-pin (4-step baseline+confirmation) ---\n");
    printf("  Note: INCONCLUSIVE = pin held by radio, verify with multimeter\n");
    fflush(stdout);
    int inconclusive_count = 0;
    for (int i = 0; i < pair_count; i++) {
        const PinDef *a = &pins[pairs[i].a_idx];
        const PinDef *b = &pins[pairs[i].b_idx];
        PairResult result = test_pin_pair(a, b);

        const char *status;
        switch (result) {
            case PAIR_OK:
                status = "OK";
                break;
            case PAIR_SHORT:
                status = "SHORT CONFIRMED";
                total_shorts++;
                break;
            case PAIR_INCONCLUSIVE:
                status = "INCONCLUSIVE (held by radio)";
                inconclusive_count++;
                break;
            default:
                status = "UNKNOWN";
                break;
        }
        printf("  %-4s-%-4s (%-5s-%-5s): %s\n",
               a->name, b->name, a->function, b->function, status);
        fflush(stdout);
    }
    printf("\n");

    printf("=============================================\n");
    printf("  SUMMARY\n");
    printf("  Shorts/Issues found: %d\n", total_shorts);
    printf("  Inconclusive pairs:  %d (verify with multimeter)\n", inconclusive_count);
    if (total_shorts == 0) {
        printf("  RESULT: ALL CLEAR - safe to proceed\n");
    } else {
        printf("  RESULT: FAIL - fix %d short(s) before proceeding\n", total_shorts);
    }
    printf("=============================================\n");
    printf("\n");
    fflush(stdout);

    ESP_LOGI(TAG, "Test complete. LED pattern:");
    ESP_LOGI(TAG, "  All clear:  1 slow blink / 2s");
    ESP_LOGI(TAG, "  1 short:    2 fast blinks + 2s pause");
    ESP_LOGI(TAG, "  2 shorts:   3 fast blinks + 2s pause");
    ESP_LOGI(TAG, "  3+ shorts:  5 fast blinks + 2s pause");

    while (true) {
        if (total_shorts == 0) {
            blink(1, 1000, 1000);
            vTaskDelay(pdMS_TO_TICKS(2000));
        } else if (total_shorts == 1) {
            blink(2, 150, 150);
            vTaskDelay(pdMS_TO_TICKS(2000));
        } else if (total_shorts == 2) {
            blink(3, 150, 150);
            vTaskDelay(pdMS_TO_TICKS(2000));
        } else {
            blink(5, 150, 150);
            vTaskDelay(pdMS_TO_TICKS(2000));
        }
    }
}

#endif
