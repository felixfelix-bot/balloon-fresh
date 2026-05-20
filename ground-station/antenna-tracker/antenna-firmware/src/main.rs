use esp_idf_hal::delay::FreeRtos;
use esp_idf_hal::gpio::*;
use esp_idf_hal::prelude::*;
use esp_idf_hal::uart::{config::Config as UartConfig, UartDriver};

// 28BYJ-48 half-step sequence
const STEP_SEQUENCE: [[u8; 4]; 8] = [
    [1, 0, 0, 0],
    [1, 1, 0, 0],
    [0, 1, 0, 0],
    [0, 1, 1, 0],
    [0, 0, 1, 0],
    [0, 0, 1, 1],
    [0, 0, 0, 1],
    [1, 0, 0, 1],
];

struct Stepper<'a, IN1, IN2, IN3, IN4>
where
    IN1: OutputPin,
    IN2: OutputPin,
    IN3: OutputPin,
    IN4: OutputPin,
{
    pin1: PinDriver<'a, IN1, Output>,
    pin2: PinDriver<'a, IN2, Output>,
    pin3: PinDriver<'a, IN3, Output>,
    pin4: PinDriver<'a, IN4, Output>,
    index: i32,
}

impl<'a, IN1, IN2, IN3, IN4> Stepper<'a, IN1, IN2, IN3, IN4>
where
    IN1: OutputPin,
    IN2: OutputPin,
    IN3: OutputPin,
    IN4: OutputPin,
{
    fn new(
        pin1: PinDriver<'a, IN1, Output>,
        pin2: PinDriver<'a, IN2, Output>,
        pin3: PinDriver<'a, IN3, Output>,
        pin4: PinDriver<'a, IN4, Output>,
    ) -> Self {
        Self {
            pin1,
            pin2,
            pin3,
            pin4,
            index: 0,
        }
    }

    fn step(&mut self, direction: i32) {
        self.index += direction;
        if self.index > 7 {
            self.index = 0;
        }
        if self.index < 0 {
            self.index = 7;
        }

        let pattern = STEP_SEQUENCE[self.index as usize];
        if pattern[0] == 1 {
            self.pin1.set_high().unwrap();
        } else {
            self.pin1.set_low().unwrap();
        }

        if pattern[1] == 1 {
            self.pin2.set_high().unwrap();
        } else {
            self.pin2.set_low().unwrap();
        }

        if pattern[2] == 1 {
            self.pin3.set_high().unwrap();
        } else {
            self.pin3.set_low().unwrap();
        }

        if pattern[3] == 1 {
            self.pin4.set_high().unwrap();
        } else {
            self.pin4.set_low().unwrap();
        }

        FreeRtos::delay_ms(2);
    }

    fn move_steps(&mut self, steps: i32) {
        let dir = if steps >= 0 { 1 } else { -1 };
        for _ in 0..steps.abs() {
            self.step(dir);
        }
    }
}

fn main() -> anyhow::Result<()> {
    esp_idf_sys::link_patches();

    let peripherals = Peripherals::take().unwrap();
    let pins = peripherals.pins;

    // Azimuth motor GPIOs
    let mut az = Stepper::new(
        PinDriver::output(pins.gpio14)?,
        PinDriver::output(pins.gpio27)?,
        PinDriver::output(pins.gpio26)?,
        PinDriver::output(pins.gpio25)?,
    );

    // Elevation motor GPIOs
    let mut el = Stepper::new(
        PinDriver::output(pins.gpio33)?,
        PinDriver::output(pins.gpio32)?,
        PinDriver::output(pins.gpio18)?,
        PinDriver::output(pins.gpio19)?,
    );

    println!("Antenna tracker ready.");
    println!("Commands:");
    println!("  AZ <steps>");
    println!("  EL <steps>");
    println!("Baud: 115200");

    // Use UART0 (USB serial) instead of blocking stdin()
    // Explicitly set baudrate to avoid relying on defaults
    let config = UartConfig::default().baudrate(115_200.Hz());
    let mut uart = UartDriver::new(
        peripherals.uart0,
        pins.gpio1, // TX
        pins.gpio3, // RX
        Option::<AnyIOPin>::None,
        Option::<AnyIOPin>::None,
        &config,
    )?;

    let mut buffer = [0u8; 64];

    loop {
        match uart.read(&mut buffer, 10) {
            Ok(n) if n > 0 => {
                let input = String::from_utf8_lossy(&buffer[..n]);
                let trimmed = input.trim();

                if trimmed.starts_with("AZ") {
                    if let Ok(val) = trimmed[2..].trim().parse::<i32>() {
                        println!("[FW] Received AZ command: {} steps", val);
                        println!("[FW] Moving azimuth...");
                        az.move_steps(val);
                        println!("[FW] Azimuth move complete");
                        println!("AZ done");
                    }
                } else if trimmed.starts_with("EL") {
                    if let Ok(val) = trimmed[2..].trim().parse::<i32>() {
                        println!("[FW] Received EL command: {} steps", val);
                        println!("[FW] Moving elevation...");
                        el.move_steps(val);
                        println!("[FW] Elevation move complete");
                        println!("EL done");
                    }
                }
            }
            _ => {}
        }

        FreeRtos::delay_ms(5);
    }
}
