#pragma once

#define ESP_OK 0
#define ESP_ERR_NOT_FOUND (-2)
#define ESP_ERROR_CHECK(x) do { int _rc = (x); (void)_rc; } while(0)
typedef int esp_err_t;
