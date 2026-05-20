#include "sky66112.h"
#include "driver/gpio.h"
#include "esp_log.h"

static const char *TAG = "SKY66112";

static int s_tx_en = -1;
static int s_rx_en = -1;

esp_err_t sky66112_init(int tx_en_pin, int rx_en_pin)
{
    s_tx_en = tx_en_pin;
    s_rx_en = rx_en_pin;

    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << tx_en_pin) | (1ULL << rx_en_pin),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&io_conf);

    sky66112_shutdown();
    ESP_LOGI(TAG, "SKY66112 FEM initialized (TX_EN=%d, RX_EN=%d)", tx_en_pin, rx_en_pin);
    return ESP_OK;
}

esp_err_t sky66112_set_mode(sky66112_mode_t mode)
{
    switch (mode) {
    case SKY66112_MODE_TX:
        gpio_set_level(s_tx_en, 1);
        gpio_set_level(s_rx_en, 0);
        break;
    case SKY66112_MODE_RX:
        gpio_set_level(s_tx_en, 0);
        gpio_set_level(s_rx_en, 1);
        break;
    case SKY66112_MODE_BYPASS:
        gpio_set_level(s_tx_en, 1);
        gpio_set_level(s_rx_en, 1);
        break;
    case SKY66112_MODE_SHUTDOWN:
        gpio_set_level(s_tx_en, 0);
        gpio_set_level(s_rx_en, 0);
        break;
    }
    return ESP_OK;
}

esp_err_t sky66112_tx_enable(void)
{
    return sky66112_set_mode(SKY66112_MODE_TX);
}

esp_err_t sky66112_tx_disable(void)
{
    return sky66112_set_mode(SKY66112_MODE_SHUTDOWN);
}

esp_err_t sky66112_rx_enable(void)
{
    return sky66112_set_mode(SKY66112_MODE_RX);
}

esp_err_t sky66112_shutdown(void)
{
    return sky66112_set_mode(SKY66112_MODE_SHUTDOWN);
}
