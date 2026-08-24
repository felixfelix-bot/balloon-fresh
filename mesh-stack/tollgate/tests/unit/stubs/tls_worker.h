#ifndef STUBS_TLS_WORKER_H
#define STUBS_TLS_WORKER_H

#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

void tls_worker_set_queue(QueueHandle_t q);
void tls_worker_submit(const char *token);

#endif
