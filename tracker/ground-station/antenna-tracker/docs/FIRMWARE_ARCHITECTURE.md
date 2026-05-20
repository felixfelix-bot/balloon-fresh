# Firmware Architecture

## Stepper Driver Design

Generic implementation:

```
Stepper<'a, IN1, IN2, IN3, IN4>
```

Each pin stored as:

```
PinDriver<'a, INx, Output>
```

Avoid:
- `AnyOutputPin`
- `.into()` conversions
- Arrays of generic pin types

Reason: Prevents E0283 type inference failures.

---

## Step Mode

Half-step sequence (8-step pattern) for 28BYJ-48.

Delay per step:
```
FreeRtos::delay_ms(2);
```

---

## UART

Replaced blocking `stdin()` with:

```
UartDriver::new(peripherals.uart0, gpio1, gpio3, ...)
```

Non-blocking read:

```
uart.read(&mut buffer, 10)
```

FreeRTOS yield:

```
FreeRtos::delay_ms(5);
```

Prevents task watchdog starvation.
