#pragma once

#include <stdint.h>

typedef void (*cli_cmd_handler)(const char *args);

void cli_init(void);
void cli_process(void);
void cli_register_command(const char *name, const char *help, cli_cmd_handler handler);
void cli_set_io(int (*getchar_fn)(void), void (*printf_fn)(const char *, ...));
