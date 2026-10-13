# Task Report: t_80a4ae44

- Updated `tracker/hardware/PINOUT_VERIFICATION.md` V1-FAST table.
- GPIO9 LED row is now obsolete/do-not-populate and documents the boot-mode strap/download-boot hazard.
- GPIO18 is identified as the current firmware LED pin, matching `app_main.cpp` (`LED_GPIO 18`).
- Checked all sibling V1-FAST radio rows against `app_main.cpp`: SCK 6, MISO 2, MOSI 7, NSS 10, BUSY 4, RST 3, DIO9 5; no additional mismatches found.
- V2-ADC table was not modified.
- Verification: `PYTHON=/usr/bin/python3 make test-unit` — 33 passed.
- `git diff --check` passed.
- Commit: d082b418662f1099d049c4f1551c105f0c5b0c55.
- Push status pending at report creation.
