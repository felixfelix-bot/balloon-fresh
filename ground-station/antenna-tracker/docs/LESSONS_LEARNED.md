# Lessons Learned

## 1. IDF Version Compatibility
- IDF v6.x is incompatible with esp-idf-sys 0.36.x
- Downgrade to v5.3

## 2. Xtensa Toolchain
- Stable Rust does not support Xtensa
- Must use Espressif Rust toolchain

## 3. GCC Conflicts
- Rust toolchain installs GCC 15.x
- IDF v5.3 requires GCC 13.2.0
- Remove Rust’s bundled Xtensa GCC

## 4. GPIO Generics
- Do not use `AnyOutputPin` with `.into()`
- Use concrete generic parameters

## 5. FreeRTOS Watchdog
- Blocking calls starve IDLE task
- Always yield with `FreeRtos::delay_ms()`

## 6. Avoid std::io on ESP
- `stdin()` uses pthread mutexes
- Can trigger watchdog or deadlocks
- Use HAL drivers instead
