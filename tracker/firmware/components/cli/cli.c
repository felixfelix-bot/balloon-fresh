#include "cli.h"
#include <string.h>
#include <stdio.h>

#define CLI_MAX_CMDS 16
#define CLI_BUF_SIZE 128

typedef struct {
    const char *name;
    const char *help;
    cli_cmd_handler handler;
} cli_cmd_t;

static cli_cmd_t s_cmds[CLI_MAX_CMDS];
static uint8_t s_num_cmds;
static char s_buf[CLI_BUF_SIZE];
static uint16_t s_buf_pos;

static int (*s_getchar_fn)(void) = NULL;
static void (*s_printf_fn)(const char *, ...) = NULL;

void cli_set_io(int (*getchar_fn)(void), void (*printf_fn)(const char *, ...)) {
    s_getchar_fn = getchar_fn;
    s_printf_fn = printf_fn;
}

#define CLI_GETCHAR() (s_getchar_fn ? s_getchar_fn() : getchar())
#define CLI_PRINTF(...) do { if (s_printf_fn) s_printf_fn(__VA_ARGS__); else printf(__VA_ARGS__); } while(0)

static void cmd_help(const char *args) {
    (void)args;
    CLI_PRINTF("Available commands:\n");
    for (uint8_t i = 0; i < s_num_cmds; i++) {
        CLI_PRINTF("  %-12s %s\n", s_cmds[i].name, s_cmds[i].help);
    }
}

void cli_init(void) {
    s_num_cmds = 0;
    s_buf_pos = 0;
    memset(s_buf, 0, sizeof(s_buf));
    cli_register_command("help", "List available commands", cmd_help);
}

void cli_register_command(const char *name, const char *help, cli_cmd_handler handler) {
    if (s_num_cmds >= CLI_MAX_CMDS) return;
    s_cmds[s_num_cmds].name = name;
    s_cmds[s_num_cmds].help = help;
    s_cmds[s_num_cmds].handler = handler;
    s_num_cmds++;
}

void cli_process(void) {
    int ch = CLI_GETCHAR();
    if (ch == EOF) return;

    if (ch == '\r' || ch == '\n') {
        if (s_buf_pos == 0) return;
        s_buf[s_buf_pos] = '\0';
        CLI_PRINTF("\n");

        char *space = strchr(s_buf, ' ');
        char *args = NULL;
        if (space) {
            *space = '\0';
            args = space + 1;
        }

        int found = 0;
        for (uint8_t i = 0; i < s_num_cmds; i++) {
            if (strcmp(s_buf, s_cmds[i].name) == 0) {
                s_cmds[i].handler(args ? args : "");
                found = 1;
                break;
            }
        }
        if (!found) {
            CLI_PRINTF("Unknown command: %s (type 'help')\n", s_buf);
        }

        s_buf_pos = 0;
        memset(s_buf, 0, sizeof(s_buf));
        CLI_PRINTF("> ");
    } else if (ch == 0x7F || ch == 0x08) {
        if (s_buf_pos > 0) {
            s_buf_pos--;
            s_buf[s_buf_pos] = '\0';
        }
    } else if (s_buf_pos < CLI_BUF_SIZE - 1) {
        s_buf[s_buf_pos++] = (char)ch;
    }
}
