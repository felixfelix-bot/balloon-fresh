#include <stdio.h>
#include <string.h>
#include <assert.h>
#include <stdarg.h>

#include "../cli.c"

static char s_input_buf[256];
static int s_input_pos;
static int s_input_len;

static char s_output_buf[1024];
static int s_output_pos;

static int test_getchar(void) {
    if (s_input_pos >= s_input_len) return EOF;
    return s_input_buf[s_input_pos++];
}

static void test_printf(const char *fmt, ...) {
    va_list ap;
    va_start(ap, fmt);
    s_output_pos += vsnprintf(s_output_buf + s_output_pos,
                               sizeof(s_output_buf) - s_output_pos, fmt, ap);
    va_end(ap);
}

static void feed(const char *str) {
    s_input_pos = 0;
    s_input_len = (int)strlen(str);
    memcpy(s_input_buf, str, s_input_len);
    s_output_pos = 0;
    s_output_buf[0] = '\0';
    while (s_input_pos < s_input_len) {
        cli_process();
    }
}

static int s_handler_called;
static char s_handler_args[64];

static void test_handler(const char *args) {
    s_handler_called = 1;
    strncpy(s_handler_args, args, sizeof(s_handler_args) - 1);
}

static void test_init_registers_help(void) {
    cli_init();
    cli_set_io(test_getchar, test_printf);
    assert(s_num_cmds >= 1);
    assert(strcmp(s_cmds[0].name, "help") == 0);
    printf("PASS\n");
}

static void test_register_and_dispatch(void) {
    cli_init();
    cli_set_io(test_getchar, test_printf);
    s_handler_called = 0;
    cli_register_command("test", "Test cmd", test_handler);
    feed("test\n");
    assert(s_handler_called == 1);
    printf("PASS\n");
}

static void test_dispatch_with_args(void) {
    cli_init();
    cli_set_io(test_getchar, test_printf);
    s_handler_called = 0;
    memset(s_handler_args, 0, sizeof(s_handler_args));
    cli_register_command("set", "Set value", test_handler);
    feed("set foo=bar\n");
    assert(s_handler_called == 1);
    assert(strcmp(s_handler_args, "foo=bar") == 0);
    printf("PASS (args='%s')\n", s_handler_args);
}

static void test_unknown_command(void) {
    cli_init();
    cli_set_io(test_getchar, test_printf);
    feed("xyz\n");
    assert(strstr(s_output_buf, "Unknown command") != NULL);
    printf("PASS\n");
}

static void test_backspace(void) {
    cli_init();
    cli_set_io(test_getchar, test_printf);
    s_handler_called = 0;
    cli_register_command("hello", "Hello", test_handler);
    feed("hellx\x7Fo\n");
    assert(s_handler_called == 1);
    printf("PASS\n");
}

static void test_empty_line_ignored(void) {
    cli_init();
    cli_set_io(test_getchar, test_printf);
    s_handler_called = 0;
    cli_register_command("test", "Test", test_handler);
    feed("\n");
    assert(s_handler_called == 0);
    printf("PASS\n");
}

static void test_multiple_commands(void) {
    cli_init();
    cli_set_io(test_getchar, test_printf);
    int call_count = 0;
    cli_register_command("cnt", "Count", test_handler);

    s_handler_called = 0;
    feed("cnt\n");
    call_count += s_handler_called;

    s_handler_called = 0;
    feed("cnt\n");
    call_count += s_handler_called;

    assert(call_count == 2);
    printf("PASS\n");
}

static void test_buffer_overflow(void) {
    cli_init();
    cli_set_io(test_getchar, test_printf);
    s_handler_called = 0;
    cli_register_command("test", "Test", test_handler);

    char long_input[200];
    memset(long_input, 'A', 127);
    long_input[127] = '\n';
    long_input[128] = '\0';
    feed(long_input);

    assert(s_handler_called == 0);
    assert(strstr(s_output_buf, "Unknown command") != NULL);
    printf("PASS\n");
}

int main(void) {
    printf("\n=== CLI Tests ===\n\n");

    printf("TEST 1: init registers help... ");
    test_init_registers_help();
    printf("TEST 2: register and dispatch... ");
    test_register_and_dispatch();
    printf("TEST 3: dispatch with args... ");
    test_dispatch_with_args();
    printf("TEST 4: unknown command... ");
    test_unknown_command();
    printf("TEST 5: backspace handling... ");
    test_backspace();
    printf("TEST 6: empty line ignored... ");
    test_empty_line_ignored();
    printf("TEST 7: multiple commands... ");
    test_multiple_commands();
    printf("TEST 8: buffer overflow... ");
    test_buffer_overflow();

    printf("\n=== Results: 8/8 passed ===\n");
    return 0;
}
