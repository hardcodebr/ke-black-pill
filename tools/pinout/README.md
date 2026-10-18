# Pinout graphic generator

`make_pinout.py` draws the HardCode pinout graphics (board photo in the middle,
one colour chip per pin function) as SVG + PNG.

```sh
python3 -m venv ~/codex_jobs/ke_pinout/venv && ~/codex_jobs/ke_pinout/venv/bin/pip install cairosvg pillow
~/codex_jobs/ke_pinout/venv/bin/python make_pinout.py boards/hc26060.json        # -> docs/img/pinout_ke02/ke04.png + .svg
~/codex_jobs/ke_pinout/venv/bin/python make_pinout.py boards/hc26060.json -v ke04
```

| File | What |
|---|---|
| `palette.json` | **Shared HardCode palette**: one colour per function class (power, GND, reset/boot, port, UART, SPI, I2C, PWM, ADC, comparator, KBI, misc, USB), signal-name rules, fonts. Used by every HardCode board graphic, so all boards look like one family. |
| `boards/<board>.json` | One board: photo, measured hole positions (pixels in the photo crop), header rows, info boxes, variants, layout (pitch, columns). |
| `HC26060_pin_table.csv` | Pin table for this board. **Copy** — the master is `hardcode_coo/products/KinetisKEModule/pinout/HC26060_pin_table.csv`. Edit the master, then copy it here and re-run. |
| `photos/` | Cropped board photos (white background) the graphics are built on. |

Rules the script enforces: every chip text is measured with the real font (shrinks at most
to 78 %, else it stops), and every placed box is checked for overlaps — it stops with an
error instead of drawing a clash. Each function class gets a fixed column where possible
(capped by `max_slots`; a clashing chip moves to the nearest free column on that row).

Two layouts:
- `rows` (default) — two long pin rows beside the photo (KE Black Pill, `boards/hc26060.json`).
- `callouts` (`"layout": {"mode": "callouts"}`) — chips in rows beside / above / below the photo,
  joined by leader lines; for boards with short headers, jumpers and buttons:
  `boards/hc22002.json` (USB-C ESP Programmer) and `boards/hc22003.json` (isolated version).
  Their `out_dir` points at the sibling repos (`usb-esp-programmer/docs/img`, `usb-esp-programmer-isolated/docs/img`).
