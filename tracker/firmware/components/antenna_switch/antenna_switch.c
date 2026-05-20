#include "antenna_switch.h"
#include "driver/gpio.h"
#include "esp_log.h"

static const char *TAG = "ANT_SW";

static int s_ctrl1 = -1;
static int s_ctrl2 = -1;
static uint8_t s_current = 0;

static const uint8_t ant_table[4][2] = {
    {0, 0},
    {1, 0},
    {0, 1},
    {1, 1},
};

esp_err_t antenna_switch_init(int ctrl1_pin, int ctrl2_pin)
{
    s_ctrl1 = ctrl1_pin;
    s_ctrl2 = ctrl2_pin;

    gpio_config_t io_conf = {
        .pin_bit_mask = (1ULL << ctrl1_pin) | (1ULL << ctrl2_pin),
        .mode = GPIO_MODE_OUTPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_DISABLE,
    };
    gpio_config(&io_conf);

    antenna_switch_select(0);
    ESP_LOGI(TAG, "SP4T antenna switch initialized (GPIO%d, GPIO%d)", ctrl1_pin, ctrl2_pin);
    return ESP_OK;
}

esp_err_t antenna_switch_select(uint8_t antenna)
{
    if (antenna > 3) {
        ESP_LOGW(TAG, "Invalid antenna %d, clamping to 3", antenna);
        antenna = 3;
    }

    gpio_set_level(s_ctrl1, ant_table[antenna][0]);
    gpio_set_level(s_ctrl2, ant_table[antenna][1]);
    s_current = antenna;
    return ESP_OK;
}

uint8_t antenna_switch_get_current(void)
{
    return s_current;
}
