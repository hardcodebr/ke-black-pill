#!/usr/bin/env python3
"""HardCode pinout graphic generator (SVG + PNG).

    make_pinout.py boards/hc26060.json            # all variants of a board
    make_pinout.py boards/hc26060.json -v ke04    # one variant
    make_pinout.py boards/hc22002.json -o ../../docs/img

Inputs
  palette.json        shared colours / function classes / fonts (all HardCode boards)
  boards/<board>.json photo + measured hole positions + header rows + info boxes
  pin table           CSV (header,pin,silk,port,type,<alternates>,board_use,notes)
                      or inline "pins" in the board JSON

The board photo sits in the middle, chips line up with the measured pin holes.
Every chip text is measured with the real font and every placed box is checked
for overlaps; the script stops with an error instead of drawing a clash.
Rendering: cairosvg (pip install cairosvg pillow).
"""
import argparse
import base64
import csv
import io
import json
import os
import re
import sys
from xml.sax.saxutils import escape

from PIL import Image, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))


# --------------------------------------------------------------------------- fonts
class Fonts:
    def __init__(self, cfg):
        self.cfg = cfg
        self.family = cfg["family"]
        self._cache = {}

    def font(self, size, weight="bold"):
        key = (round(size, 2), weight)
        if key not in self._cache:
            self._cache[key] = ImageFont.truetype(self.cfg[weight], max(1, int(round(size))))
        return self._cache[key]

    def width(self, text, size, weight="bold"):
        f = self.font(size, weight)
        return f.getlength(text) * size / max(1, int(round(size)))

    def cap(self, size):
        """Cap height (for vertical centring of text in a chip)."""
        return 0.714 * size


# --------------------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, fonts, pal):
        self.f = fonts
        self.pal = pal
        self.els = []
        self.boxes = []  # (x0,y0,x1,y1,name,group)

    # registration / overlap ------------------------------------------------
    def reg(self, x0, y0, x1, y1, name, group=None):
        self.boxes.append((x0, y0, x1, y1, name, group))

    def check(self, pad=1.0):
        bad = []
        b = self.boxes
        for i in range(len(b)):
            for j in range(i + 1, len(b)):
                a, c = b[i], b[j]
                if a[5] is not None and a[5] == c[5]:
                    continue
                if a[0] < c[2] - pad and c[0] < a[2] - pad and a[1] < c[3] - pad and c[1] < a[3] - pad:
                    bad.append((a[4], c[4]))
        return bad

    # primitives -------------------------------------------------------------
    def rect(self, x, y, w, h, fill, rx=0, stroke=None, sw=0, dash=None, opacity=None):
        s = f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx:.1f}" fill="{fill}"'
        if stroke:
            s += f' stroke="{stroke}" stroke-width="{sw}"'
        if dash:
            s += f' stroke-dasharray="{dash}"'
        if opacity is not None:
            s += f' opacity="{opacity}"'
        self.els.append(s + "/>")

    def circle(self, cx, cy, r, fill, stroke=None, sw=0):
        s = f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}"'
        if stroke:
            s += f' stroke="{stroke}" stroke-width="{sw}"'
        self.els.append(s + "/>")

    def line(self, pts, color, w=2, dash=None):
        p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        s = f'<polyline points="{p}" fill="none" stroke="{color}" stroke-width="{w}" stroke-linejoin="round" stroke-linecap="round"'
        if dash:
            s += f' stroke-dasharray="{dash}"'
        self.els.append(s + "/>")

    def text(self, x, y, txt, size, color, weight="bold", anchor="start", opacity=None):
        """y = baseline."""
        fw = {"bold": "bold", "regular": "normal", "italic": "normal"}[weight]
        st = ' font-style="italic"' if weight == "italic" else ""
        op = f' opacity="{opacity}"' if opacity is not None else ""
        self.els.append(
            f'<text x="{x:.1f}" y="{y:.1f}" font-family="{self.f.family}" font-size="{size:.1f}" '
            f'font-weight="{fw}"{st} fill="{color}" text-anchor="{anchor}"{op}>{escape(txt)}</text>')

    def image(self, x, y, w, h, path):
        im = Image.open(path).convert("RGB")
        im = im.resize((max(1, int(round(w * 1.5))), max(1, int(round(h * 1.5)))), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=90)
        data = base64.b64encode(buf.getvalue()).decode()
        self.els.append(f'<image x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
                        f'preserveAspectRatio="none" href="data:image/jpeg;base64,{data}"/>')

    # chip -------------------------------------------------------------------
    def chip(self, x, yc, w, h, cls, txt, fs, name=None, faded=False, group=None, outline=False):
        c = self.pal["classes"][cls]
        y = yc - h / 2
        op = None
        if faded:
            self.rect(x, y, w, h, tint(c["fill"], 0.16), rx=h * 0.24, stroke=tint(c["fill"], 0.55), sw=2, dash="6 4")
            col = shade(c["fill"], 0.85) if c["text"] == "#FFFFFF" else c["text"]
        elif outline:
            self.rect(x, y, w, h, "#FFFFFF", rx=h * 0.24, stroke=c["fill"], sw=2.5)
            col = c["fill"]
        else:
            self.rect(x, y, w, h, c["fill"], rx=h * 0.24)
            col = c["text"]
        size = fit_size(self.f, txt, fs, w - 2 * PAD_X(h))
        self.text(x + w / 2, yc + self.f.cap(size) / 2, txt, size, col, anchor="middle", opacity=op)
        self.reg(x, y, x + w, y + h, name or txt, group)

    def svg(self, w, h, bg="#FFFFFF"):
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" '
                f'viewBox="0 0 {w:.0f} {h:.0f}">\n<rect width="100%" height="100%" fill="{bg}"/>\n'
                + "\n".join(self.els) + "\n</svg>\n")


def PAD_X(h):
    return h * 0.22


def fit_size(fonts, txt, fs, maxw, min_ratio=0.78):
    w = fonts.width(txt, fs)
    if w <= maxw:
        return fs
    size = fs * maxw / w
    if size < fs * min_ratio:
        raise SystemExit(f"text does not fit: {txt!r} needs {w:.0f}px > {maxw:.0f}px")
    return size


def wrap(fonts, txt, size, maxw, weight="regular"):
    lines, cur = [], ""
    for word in txt.split():
        t = (cur + " " + word).strip()
        if fonts.width(t, size, weight) <= maxw or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    for ln in lines:
        if fonts.width(ln, size, weight) > maxw:
            raise SystemExit(f"word too long for box: {ln!r}")
    return lines


# --------------------------------------------------------------------------- data
def classify(pal, sig):
    for rx, cls in pal["rules"]:
        if re.search(rx, sig):
            return cls
    return "sys"


def load_pins(board, board_dir, variant):
    if "pins" in board:
        return board["pins"]
    path = os.path.join(board_dir, board["pin_table"])
    with open(path, newline="") as fh:
        rows = [ln for ln in fh if not ln.lstrip().startswith("#")]
    out = []
    altcol = variant["alt_column"]
    for r in csv.DictReader(rows):
        alts = [a.strip() for a in r[altcol].split(";") if a.strip()]
        notes = r["notes"].strip()
        flags = [t for t in re.split(r"[;,\s]+", notes) if t in ("hd", "od")]
        out.append(dict(header=r["header"], pin=int(r["pin"]), silk=r["silk"], port=r["port"],
                        type=r["type"], alts=alts, flags=flags, board_use=r["board_use"]))
    return out


def pin_chips(pal, p):
    """-> (name_chip, [alternate chips]); chip = (class, text, faded)."""
    t = p["type"]
    if t == "power":
        return ("power", p["silk"], False), []
    if t == "gnd":
        return ("gnd", "GND", False), []
    if t == "reset":
        alts = [("port", p["port"], True)] + [(classify(pal, a), a, True) for a in p["alts"] if a != "RESET"]
        return ("ctrl", "RESET", False), alts
    if t in ("ctrl", "uart", "usb"):
        return (t, p["silk"], False), [(classify(pal, a), a, False) for a in p.get("alts", [])]
    return ("port", p["port"], False), [(classify(pal, a), ALIASES.get(a, a), False) for a in p["alts"]]


ALIASES = {}
CLASS_ORDER = ["kbi", "uart", "spi", "i2c", "pwm", "adc", "acmp", "ctrl", "sys"]


def assign_slots(rows, max_slots=None):
    """Give each function class a home column, so the colours line up like the
    reference pinouts. Classes share a column when they never meet on one pin
    (exact colouring). If that needs more than max_slots columns, the columns are
    capped and a clashing chip moves to the nearest free column on that row only.
    Returns ([{slot: chip} per row], number_of_slots)."""
    per_pin = []
    for chips in rows:
        seen, keys = {}, []
        for cls, _, _ in chips:
            k = seen.get(cls, 0)
            seen[cls] = k + 1
            keys.append(f"{cls}#{k}")
        per_pin.append(keys)
    allkeys = []
    for cls in CLASS_ORDER + sorted({k.split("#")[0] for ks in per_pin for k in ks} - set(CLASS_ORDER)):
        for n in range(4):
            k = f"{cls}#{n}"
            if any(k in ks for ks in per_pin):
                allkeys.append(k)
    conflict = {k: {} for k in allkeys}
    for ks in per_pin:
        for x in ks:
            for y in ks:
                if x != y:
                    conflict[x][y] = conflict[x].get(y, 0) + 1
    widest = max([len(ks) for ks in per_pin] + [1])
    where = {}
    n = widest
    found = False
    while not found and n <= len(allkeys) and (max_slots is None or n <= max_slots):
        where = {}

        def solve(i):
            if i == len(allkeys):
                return True
            k = allkeys[i]
            used = {where[c] for c in conflict[k] if c in where}
            for col in range(n):
                if col not in used:
                    where[k] = col
                    if solve(i + 1):
                        return True
                    del where[k]
            return False
        found = solve(0)
        if not found:
            n += 1
    if not found:  # capped: greedy, fewest clashes
        n = max_slots
        where = {}
        for k in allkeys:
            cost = [sum(c for o, c in conflict[k].items() if where.get(o) == col) for col in range(n)]
            where[k] = cost.index(min(cost))
    out = []
    for chips, ks in zip(rows, per_pin):
        row = {}
        pending = []
        for chip, k in zip(chips, ks):
            if where[k] in row:
                pending.append((chip, where[k]))
            else:
                row[where[k]] = chip
        for chip, home in pending:
            free = sorted((c for c in range(n) if c not in row), key=lambda c: (abs(c - home), -c))
            if not free:
                raise SystemExit("more chips on one pin than columns")
            row[free[0]] = chip
        out.append(row)
    return out, n


# --------------------------------------------------------------------------- main build
def build(board, board_dir, vkey, pal, out_dir, cfg):
    V = board["variants"][vkey]
    F = Fonts(pal["fonts"])
    C = Canvas(F, pal)
    ink, muted = pal["ink"], pal["muted"]

    PITCH = cfg["pitch"]
    H = PITCH * 0.80          # chip height
    FS = H * 0.52             # chip font
    GAP = 6                   # gap between chips
    M = 60                    # outer margin

    ALIASES.clear()
    ALIASES.update(board.get("aliases", {}))
    pins = load_pins(board, board_dir, V)
    tp = board["top_photo"]
    rows_cfg = tp["rows"]
    by_hdr = {}
    for p in pins:
        by_hdr.setdefault(p["header"], {})[p["pin"]] = p

    # photo scale: measured hole pitch -> PITCH
    any_row = next(iter(rows_cfg.values()))
    ph_pitch = abs(any_row["p1"][1] - any_row["pN"][1]) / (any_row["n"] - 1)
    s = PITCH / ph_pitch
    bx0, by0, bx1, by1 = tp["board_box"]
    pw, phh = (bx1 - bx0) * s, (by1 - by0) * s

    # chips per row + column widths
    side_rows = {}
    for hname, rc in rows_cfg.items():
        side_rows[hname] = [pin_chips(pal, by_hdr[hname][i]) for i in range(1, rc["n"] + 1)]
    all_alt_rows = [alts for rs in side_rows.values() for _, alts in rs]
    rowslots, nslots = assign_slots(all_alt_rows, cfg.get("max_slots"))
    it = iter(rowslots)
    slot_rows = {h: [next(it) for _ in rs] for h, rs in side_rows.items()}

    def chip_w(txt):
        return F.width(txt, FS) + 2 * PAD_X(H)

    name_w = max(chip_w(n[1]) for rs in side_rows.values() for n, _ in rs)
    name_w = max(name_w, chip_w("PTA0"))
    slot_w = [0.0] * nslots
    for rows_ in slot_rows.values():
        for row in rows_:
            for i, (cls, txt, _) in row.items():
                slot_w[i] = max(slot_w[i], min(chip_w(txt), cfg.get("max_chip", 999)))
    has_flags = any(p["flags"] for p in pins)
    flag_w = F.width("HD", FS * 0.8) + 2 * PAD_X(H) * 0.8 if has_flags else 0
    NUM_W = F.width("20", FS) + 14
    lead = 26 if False else 18   # board edge -> pin number
    side_w = lead + NUM_W + 10 + name_w + GAP + (flag_w + GAP if has_flags else 0) + sum(slot_w) + GAP * (nslots - 1)

    W = max(2 * M + 2 * side_w + pw, cfg.get("min_width", 0))
    if os.environ.get("PINOUT_DEBUG"):
        print("W", W, "side", side_w, "name", name_w, "slots", [round(x) for x in slot_w], "photo", pw, phh, file=sys.stderr)
    # board x position (centred)
    px = (W - pw) / 2

    # ------------------------------------------------------------------ title
    y = M
    C.text(M, y + 58, V["title"], 62, ink)
    C.reg(M, y, M + F.width(V["title"], 62), y + 72, "title")
    C.text(M, y + 104, V["subtitle"], 28, muted, weight="regular")
    C.reg(M, y + 80, M + F.width(V["subtitle"], 28, "regular"), y + 112, "subtitle")
    y_title_end = y + 130

    # ------------------------------------------------------------------ top view
    th = tp.get("top_header")
    above = 175 if th else 40
    py = y_title_end + above
    C.image(px, py, pw, phh, os.path.join(board_dir, tp["file"]))
    C.reg(px, py, px + pw, py + phh, "photo-top", "photo-top")

    def to_canvas(pt):
        return px + (pt[0] - bx0) * s, py + (pt[1] - by0) * s

    FS_NUM = FS * 0.92
    for hname, rc in rows_cfg.items():
        left = rc["side"] == "left"
        n = rc["n"]
        edge = px if left else px + pw
        # header label above the column
        for i in range(1, n + 1):
            t = (i - 1) / (n - 1)
            hx = rc["p1"][0] + (rc["pN"][0] - rc["p1"][0]) * t
            hy = rc["p1"][1] + (rc["pN"][1] - rc["p1"][1]) * t
            _, yc = to_canvas((hx, hy))
            name, alts = side_rows[hname][i - 1]
            sign = -1 if left else 1
            # leader from board edge
            x = edge + sign * lead
            # pin number
            num = str(i)
            nx = x + sign * NUM_W / 2
            C.text(nx, yc + F.cap(FS_NUM) / 2, num, FS_NUM, muted, anchor="middle")
            C.reg(nx - NUM_W / 2, yc - H / 2, nx + NUM_W / 2, yc + H / 2, f"{hname}.{i}#")
            C.line([(edge + sign * 3, yc), (x, yc)], pal["line"], 2)
            x += sign * (NUM_W + 10)

            def place(w, cls, txt, faded=False, outline=False, fs=FS, h=H):
                nonlocal x
                x0 = x if not left else x - w
                C.chip(x0, yc, w, h, cls, txt, fs, name=f"{hname}.{i}:{txt}", faded=faded, outline=outline)
                x += sign * (w + GAP)

            place(name_w, name[0], name[1], name[2])
            p = by_hdr[hname][i]
            if has_flags:
                if p["flags"]:
                    fl = pal["flags"][p["flags"][0]]["label"]
                    place(flag_w, "gnd", fl, outline=True, fs=FS * 0.8, h=H * 0.8)
                else:
                    x += sign * (flag_w + GAP)
            # alternates in their slots
            slot_of = slot_rows[hname][i - 1]
            xs = x
            for si in range(nslots):
                w = slot_w[si]
                if si in slot_of:
                    cls, txt, faded = slot_of[si]
                    x0 = xs if not left else xs - w
                    C.chip(x0, yc, w, H, cls, txt, FS, name=f"{hname}.{i}:{txt}", faded=faded)
                xs += sign * (w + GAP)
            # note markers (numbered circles at the row end)
            for nn in board.get("pin_notes", {}).get(p["port"], []):
                r = H * 0.36
                last = max([si for si in slot_of] + [-1])
                xe = x + sign * (sum(slot_w[:last + 1]) + GAP * (last + 1)) if last >= 0 else x
                cx = xe + sign * (r + 2)
                marker(C, F, cx, yc, r, nn, pal, name=f"{hname}.{i}:note{nn}")

        # header name above / below the column
        lab = f"{hname}"
        lx = edge + (-1 if left else 1) * (lead + NUM_W + 10)
        _, ytop = to_canvas((rc["pN"][0], rc["pN"][1]))
        yb = ytop - H / 2 - 22
        C.text(lx, yb, lab, 34, ink, anchor="end" if left else "start")
        C.reg(lx - (F.width(lab, 34) if left else 0), yb - 30, lx + (0 if left else F.width(lab, 34)), yb + 6, f"label {hname}")
        sub = "pins 1–20"
        sx = lx + (-1 if left else 1) * (F.width(lab, 34) + 14)
        C.text(sx, yb, sub, 22, muted, weight="regular", anchor="end" if left else "start")
        sw_ = F.width(sub, 22, "regular")
        C.reg(sx - (sw_ if left else 0), yb - 20, sx + (0 if left else sw_), yb + 6, f"sub {hname}")

    # J1 (SWD) on the top view: chips fanned out above the board
    if th:
        holes = [to_canvas(hp) for hp in th["holes"]]
        labels = [pin_by_ref(pins, ref) for ref in th["pins"]]
        cw = max(chip_w(chip_label(p)) for p in labels) + 6
        total = len(holes) * cw + (len(holes) - 1) * 10
        cx0 = (holes[0][0] + holes[-1][0]) / 2 - total / 2
        ychip = py - 92
        for k, ((hx, hy), p) in enumerate(zip(holes, labels)):
            cx = cx0 + k * (cw + 10) + cw / 2
            C.line([(hx, hy), (hx, py - 26), (cx, py - 50), (cx, ychip + H / 2)], ink, 2.5)
            C.circle(hx, hy, 5, ink)
            C.chip(cx - cw / 2, ychip, cw, H, chip_class(p), chip_label(p), FS, name=f"J1top:{k}")
            sub = p["port"] if p["port"].startswith("PT") else ""
        lab = f'{th["name"]} · {th["label"]}'
        lx = cx0 + total + 18
        C.text(lx, ychip + F.cap(30) / 2, lab, 30, ink)
        C.reg(lx, ychip - 18, lx + F.width(lab, 30), ychip + 18, "J1 label")
        # port names under the label
        ports = " · ".join(p["port"] for p in labels if p["port"].startswith("PT"))
        sub = f"DIO = {labels[1]['port']} · CLK = {labels[2]['port']}"
        C.text(lx, ychip + 40, sub, 21, muted, weight="regular")
        C.reg(lx, ychip + 22, lx + F.width(sub, 21, "regular"), ychip + 46, "J1 sub")

    # USB-C callout below the board
    usb = tp.get("usb")
    y_after_top = py + phh
    if usb:
        ux, uy = to_canvas(usb["at"])
        ychip = py + phh + 50
        w = chip_w(usb["label"]) + 6
        C.line([(ux, uy), (ux, ychip - H / 2)], ink, 2.5)
        C.circle(ux, uy, 5, ink)
        C.chip(ux - w / 2, ychip, w, H, "usb", usb["label"], FS, name="usb")
        nx = ux + w / 2 + 16
        C.text(nx, ychip + F.cap(24) / 2, usb["note"], 24, muted, weight="regular")
        C.reg(nx, ychip - 14, nx + F.width(usb["note"], 24, "regular"), ychip + 14, "usb note")
        y_after_top = ychip + H / 2

    for mk in tp.get("markers", []):
        mx, my = to_canvas(mk["at"])
        ox, oy = mk.get("offset", [0, 0])
        r = H * 0.40
        cx, cy = mx + ox, my + oy
        C.line([(mx, my), (cx, cy)], "#FFFFFF", 3)
        marker(C, F, cx, cy, r, mk["n"], pal, name=f"photo marker {mk['n']}", group="photo-top", ring="#FFFFFF")

    # ------------------------------------------------------------------ bottom band
    y0 = y_after_top + 70
    C.line([(M, y0 - 30), (W - M, y0 - 30)], "#E0E6EA", 2)
    band_x = M
    bp = board.get("bottom_photo")
    band_h_parts = []
    if bp:
        bh_target = cfg.get("bottom_height", 640)
        bbx0, bby0, bbx1, bby1 = bp["board_box"]
        sb = bh_target / (bby1 - bby0)
        bw_, bh_ = (bbx1 - bbx0) * sb, (bby1 - bby0) * sb
        hdr = bp["header"]
        labels = [pin_by_ref(pins, ref) for ref in hdr["pins"]]
        cw = max(chip_w(chip_label(p)) for p in labels) + 6
        total = len(labels) * cw + (len(labels) - 1) * 10
        area_w = max(bw_, total) + 20
        bx = band_x + (area_w - bw_) / 2
        by = y0 + 150
        C.text(band_x, y0 + 26, "Bottom view", 30, ink)
        C.reg(band_x, y0, band_x + F.width("Bottom view", 30), y0 + 34, "bottom title")
        C.image(bx, by, bw_, bh_, os.path.join(board_dir, bp["file"]))
        C.reg(bx, by, bx + bw_, by + bh_, "photo-bottom", "photo-bottom")

        def b2c(pt):
            return bx + (pt[0] - bbx0) * sb, by + (pt[1] - bby0) * sb
        holes = [b2c(h) for h in hdr["holes"]]
        cx0 = (holes[0][0] + holes[-1][0]) / 2 - total / 2
        cx0 = max(cx0, band_x)
        ychip = y0 + 82
        for k, ((hx, hy), p) in enumerate(zip(holes, labels)):
            cx = cx0 + k * (cw + 10) + cw / 2
            C.line([(hx, hy), (hx, by - 14), (cx, by - 34), (cx, ychip + H / 2)], ink, 2.5)
            C.circle(hx, hy, 4.5, ink)
            C.chip(cx - cw / 2, ychip, cw, H, chip_class(p), chip_label(p), FS, name=f"J1bot:{k}")
        cap_y = by + bh_ + 34
        cap = "SWD J1: square pad = 3V3 (pin 1)"
        C.text(bx + bw_ / 2, cap_y, cap, 22, muted, weight="regular", anchor="middle")
        cwid = F.width(cap, 22, "regular")
        C.reg(bx + bw_ / 2 - cwid / 2, cap_y - 20, bx + bw_ / 2 + cwid / 2, cap_y + 6, "bottom caption")
        band_x += max(area_w, cwid) + 50
        band_h_parts.append(cap_y + 10 - y0)

    # legend
    used = []
    for rs in side_rows.values():
        for n, alts in rs:
            for cls, _, _ in [n] + alts:
                if cls not in used:
                    used.append(cls)
    for extra in ("usb",):
        if (usb and extra == "usb") and extra not in used:
            used.append(extra)
    order = list(pal["classes"].keys())
    used.sort(key=order.index)
    entries = [("chip", c, sample_text(c), pal["classes"][c]["legend"]) for c in used]
    if has_flags:
        for fk, fv in pal["flags"].items():
            if any(fk in p["flags"] for p in pins):
                entries.append(("flag", "gnd", fv["label"], fv["legend"]))
    if any(f for rs in side_rows.values() for _, alts in rs for *_, f in alts):
        entries.append(("faded", "port", "PTA5", "Only if the RESET function is off"))
    entries.append(("marker", None, None, "See the numbered note"))
    lw, lh = draw_legend(C, F, pal, entries, band_x, y0 + 10, H, FS)
    band_x += lw + 50
    band_h_parts.append(lh + 10)

    # info boxes
    infos = board.get("info", [])
    if infos:
        hh = draw_info(C, F, pal, infos, band_x, y0 + 10, W - M - band_x, cfg.get("info_cols", 2))
        band_h_parts.append(hh + 10)

    Ht = y0 + max(band_h_parts) + 40
    finish(C, F, board, V, cfg, W, Ht, out_dir, FS, M)


# --------------------------------------------------------------------------- callout layout
def build_callouts(board, board_dir, vkey, pal, out_dir, cfg):
    """Photo in the middle, chips in rows beside / above / below it, joined to the
    pins and parts by leader lines (for boards whose headers are not two long rows)."""
    V = board["variants"][vkey]
    F = Fonts(pal["fonts"])
    C = Canvas(F, pal)
    ink, muted = pal["ink"], pal["muted"]
    P = cfg.get("row_pitch", 62)
    H = cfg.get("chip_h", 46)
    FS = H * 0.52
    GAP = 8
    M = 60
    W = cfg.get("width", 2400)

    def chip_w(txt, fs=FS, h=H):
        return F.width(txt, fs) + 2 * PAD_X(h)

    ph = board["photo"]
    ox, oy = ph["origin"]
    im = Image.open(os.path.join(board_dir, ph["file"]))
    s = cfg["photo_height"] / im.size[1]
    pw, phh = im.size[0] * s, im.size[1] * s
    px = cfg.get("photo_x", (W - pw) / 2)

    # title
    y = M
    C.text(M, y + 58, V["title"], 62, ink)
    C.reg(M, y, M + F.width(V["title"], 62), y + 72, "title")
    C.text(M, y + 104, V["subtitle"], 28, muted, weight="regular")
    C.reg(M, y + 80, M + F.width(V["subtitle"], 28, "regular"), y + 112, "subtitle")
    py = y + 130 + cfg.get("space_above", 150)
    C.image(px, py, pw, phh, os.path.join(board_dir, ph["file"]))
    C.reg(px, py, px + pw, py + phh, "photo", "photo")

    def tc(pt):
        return px + (pt[0] - ox) * s, py + (pt[1] - oy) * s

    def lead(pts):
        C.line(pts, "#FFFFFF", 7)
        C.line(pts, ink, 2.5)
        C.circle(pts[0][0], pts[0][1], 6.5, ink, stroke="#FFFFFF", sw=2.5)

    def chip_spec(c):
        cls, txt = c[0], c[1]
        style = c[2] if len(c) > 2 else ""
        return cls, txt, style

    def draw_chip(x0, yc, w, c, name, h=H, fs=FS):
        cls, txt, style = chip_spec(c)
        if style != "text" and (cls == "none" or not txt):
            return
        if style == "text":
            C.text(x0, yc + F.cap(fs * 0.95) / 2, txt, fs * 0.95, muted, weight="regular")
            C.reg(x0, yc - h / 2, x0 + F.width(txt, fs * 0.95, "regular"), yc + h / 2, name)
            return
        C.chip(x0, yc, w, h, cls, txt, fs, name=name, outline=(style == "outline"))

    bottom_extent = py + phh
    top_extent = py
    right_bottom = py
    for gi, g in enumerate(board["groups"]):
        side = g["side"]
        gp = g.get("pitch", P)
        if side in ("left", "right"):
            sign = 1 if side == "right" else -1
            edge = px + pw if side == "right" else px
            rows = g["rows"]
            ncol = max(len(r["chips"]) for r in rows)
            colw = []
            for k in range(ncol):
                ws = []
                for r in rows:
                    if k < len(r["chips"]):
                        cls, txt, style = chip_spec(r["chips"][k])
                        ws.append(F.width(txt, FS * 0.95, "regular") if style == "text" else chip_w(txt))
                colw.append(max(ws + [0]))
            gap = g.get("gap", 110)
            x_start = edge + sign * gap
            if "center_y" in g:
                cy = tc((0, g["center_y"]))[1]
            else:
                cy = sum(tc(r["at"])[1] for r in rows) / len(rows)
            y0r = cy - (len(rows) - 1) * gp / 2
            numbered = g.get("numbered", False)
            NUM_W = F.width("20", FS) + 10 if numbered else 0
            for ri, r in enumerate(rows):
                yr = y0r + ri * gp
                ax, ay = tc(r["at"])
                pts = [(ax, ay)] + [tc(v) for v in r.get("via", [])]
                lx, ly = pts[-1]
                e1 = edge + sign * 22
                if (lx - e1) * sign < 0:
                    pts.append((e1, ly))
                pts += [(x_start - sign * 26, yr), (x_start, yr)]
                lead(pts)
                x = x_start
                if numbered:
                    num = str(r.get("n", ri + 1))
                    nx = x + sign * NUM_W / 2
                    C.text(nx, yr + F.cap(FS) / 2, num, FS, muted, anchor="middle")
                    C.reg(nx - NUM_W / 2, yr - H / 2, nx + NUM_W / 2, yr + H / 2, f"g{gi}r{ri}#")
                    x += sign * (NUM_W + 8)
                for k, c in enumerate(r["chips"]):
                    w = colw[k]
                    cls, txt, style = chip_spec(c)
                    if style == "text" and side == "left":
                        w = F.width(txt, FS * 0.95, "regular")
                    x0 = x if side == "right" else x - w
                    draw_chip(x0, yr, w if style != "text" else w, c, f"g{gi}r{ri}c{k}")
                    x += sign * (colw[k] + GAP)
                if side == "right":
                    right_bottom = max(right_bottom, yr + H / 2)
            if g.get("title"):
                tx = x_start + (sign * (NUM_W + 8) if numbered else 0)
                ty = y0r - H / 2 - 18
                tw = F.width(g["title"], 28)
                C.text(tx, ty, g["title"], 28, ink, anchor="start" if side == "right" else "end")
                C.reg(tx - (tw if side == "left" else 0), ty - 26, tx + (tw if side == "right" else 0), ty + 6, f"g{gi} title")
        else:  # top / bottom: one chip per item, spread horizontally, vertical leaders
            items = g["rows"]
            sign = 1 if side == "bottom" else -1
            edge = py + phh if side == "bottom" else py
            gap = g.get("gap", 70)
            yc = edge + sign * (gap + H / 2)
            placed = []
            for it_ in sorted(items, key=lambda r: tc(r["at"])[0]):
                ax, ay = tc(it_["at"])
                ws = [chip_w(chip_spec(c)[1]) for c in it_["chips"]]
                tot = sum(ws) + GAP * (len(ws) - 1)
                x0 = ax - tot / 2 + it_.get("dx", 0)
                if placed and x0 < placed[-1] + 20:
                    x0 = placed[-1] + 20
                placed.append(x0 + tot)
                cx = x0 + ws[0] / 2
                pts = [(ax, ay), (ax, edge + sign * 20), (cx, edge + sign * (gap - 14)), (cx, yc - sign * H / 2)]
                lead(pts)
                xx = x0
                for k, (c, w) in enumerate(zip(it_["chips"], ws)):
                    draw_chip(xx, yc, w, c, f"g{gi}:{k}:{chip_spec(c)[1]}")
                    xx += w + GAP
            if side == "bottom":
                bottom_extent = max(bottom_extent, yc + H / 2)
            else:
                top_extent = min(top_extent, yc - H / 2)

    # grids (2xN headers drawn as chip blocks)
    for gi, gr in enumerate(board.get("grids", [])):
        gx, gy = tc(gr["pos"]) if "pos" in gr else (0, 0)
        cells = gr["cells"]
        cw = max(chip_w(chip_spec(c)[1]) for row in cells for c in row) + 4
        ncols = max(len(row) for row in cells)
        bw = max(ncols * cw + (ncols - 1) * GAP + 28, F.width(gr["title"], 24) + 28)
        bh = len(cells) * (H + GAP) - GAP + 28 + 44
        bx = gr["x"] if "x" in gr else gx
        by = gr["y"] if "y" in gr else gy
        if gr.get("anchor") == "right_of_photo":
            bx = px + pw + gr.get("gap", 110)
            by = max(tc((0, gr["at_y"]))[1], right_bottom + 50)
            if gr.get("align") == "right":
                bx = W - M - bw
        C.rect(bx, by, bw, bh, "#F5F7F8", rx=14, stroke="#CFD8DC", sw=2)
        C.reg(bx, by, bx + bw, by + bh, f"grid{gi}", f"grid{gi}")
        C.text(bx + 14, by + 32, gr["title"], 24, ink)
        for ri, row in enumerate(cells):
            for ci, c in enumerate(row):
                cx = bx + 14 + ci * (cw + GAP)
                cyy = by + 44 + 14 + ri * (H + GAP) + H / 2
                C.chip(cx, cyy, cw, H, chip_spec(c)[0], chip_spec(c)[1], FS, group=f"grid{gi}")
        ax, ay = tc(gr["at"])
        pts = [(ax, ay)] + [tc(v) for v in gr.get("via", [])] + [(bx - 26, by + bh / 2), (bx, by + bh / 2)]
        lead(pts)
        if gr.get("note"):
            C.text(bx, by + bh + 28, gr["note"], 21, muted, weight="regular")
            C.reg(bx, by + bh + 8, bx + F.width(gr["note"], 21, "regular"), by + bh + 34, f"grid{gi} note")
            bottom_extent = max(bottom_extent, by + bh + 34)
        bottom_extent = max(bottom_extent, by + bh)

    # isolation barrier
    bar = board.get("barrier")
    if bar:
        x1, y1 = tc(bar["from"])
        x2, y2 = tc(bar["to"])
        C.line([(x1, y1), (x2, y2)], "#FFFFFF", 9, dash="16 10")
        C.line([(x1, y1), (x2, y2)], pal["classes"][bar.get("class", "ctrl")]["fill"], 4, dash="16 10")
        ytag = py - bar.get("tag_above", 32)
        for txt, anchor, dx in ((bar["left"], "end", -14), (bar["right"], "start", 14)):
            C.text(x1 + dx, ytag, txt, 24, shade(pal["classes"][bar.get("class", "ctrl")]["fill"]), anchor=anchor)
            tw = F.width(txt, 24)
            C.reg(x1 + dx - (tw if anchor == "end" else 0), ytag - 22, x1 + dx + (tw if anchor == "start" else 0), ytag + 6, f"barrier {txt}")
        C.line([(x1, ytag + 8), (x1, y1)], pal["classes"][bar.get("class", "ctrl")]["fill"], 3)

    # bottom band: legend + info boxes
    y0 = bottom_extent + 70
    C.line([(M, y0 - 30), (W - M, y0 - 30)], "#E0E6EA", 2)
    used = []
    for g in board["groups"]:
        for r in g["rows"]:
            for c in r["chips"]:
                cls, txt, style = chip_spec(c)
                if cls != "none" and style == "" and cls not in used:
                    used.append(cls)
    order = list(pal["classes"].keys())
    used.sort(key=order.index)
    names = board.get("legend_names", {})
    entries = [("chip", c, sample_text(c), names.get(c, pal["classes"][c]["legend"])) for c in used]
    for e in board.get("legend_extra", []):
        entries.append(tuple(e))
    lw, lh = draw_legend(C, F, pal, entries, M, y0 + 10, H, FS)
    hh = draw_info(C, F, pal, board.get("info", []), M + lw + 50, y0 + 10, W - 2 * M - lw - 50, cfg.get("info_cols", 2))
    Ht = y0 + 10 + max(lh, hh) + 40
    finish(C, F, board, V, cfg, W, Ht, out_dir, FS, M)


def draw_legend(C, F, pal, entries, lx0, ly0, H, FS):
    ink = pal["ink"]
    LH = H * 0.86
    LFS = 24
    sw_chip = max(F.width(e[2], FS * 0.9) + 2 * PAD_X(LH) for e in entries if e[2]) + 4
    sw_chip = max(sw_chip, 96)
    ncol = 2
    per = (len(entries) + ncol - 1) // ncol
    col_txt = [max(F.width(e[3], LFS, "regular") for e in entries[c * per:(c + 1) * per]) for c in range(ncol)]
    lw = 34 * 2 + sum(sw_chip + 14 + t for t in col_txt) + 40 * (ncol - 1)
    lh = 70 + per * (LH + 12) + 20
    C.rect(lx0, ly0, lw, lh, "#FFFFFF", rx=14, stroke="#C9A227", sw=3, dash="12 8")
    C.text(lx0 + 34, ly0 + 46, "Legend", 28, ink)
    C.reg(lx0, ly0, lx0 + lw, ly0 + lh, "legend", "legend")
    for idx, (kind, cls, txt, desc) in enumerate(entries):
        c, r = divmod(idx, per)
        ex = lx0 + 34 + sum(sw_chip + 14 + col_txt[k] + 40 for k in range(c))
        ey = ly0 + 70 + r * (LH + 12) + LH / 2
        if kind == "chip":
            C.chip(ex, ey, sw_chip, LH, cls, txt, FS * 0.9, group="legend")
        elif kind == "flag":
            C.chip(ex + (sw_chip - 60) / 2, ey, 60, LH * 0.85, "gnd", txt, FS * 0.8, outline=True, group="legend")
        elif kind == "faded":
            C.chip(ex, ey, sw_chip, LH, cls, txt, FS * 0.9, faded=True, group="legend")
        elif kind == "outline":
            C.chip(ex, ey, sw_chip, LH, cls, txt, FS * 0.9, outline=True, group="legend")
        elif kind == "marker":
            marker(C, F, ex + sw_chip / 2, ey, LH * 0.40, "n", pal, group="legend")
        C.text(ex + sw_chip + 14, ey + F.cap(LFS) / 2, desc, LFS, ink, weight="regular")
    return lw, lh


def draw_info(C, F, pal, infos, x0, y0, avail, icols):
    ink = pal["ink"]
    bw = (avail - 24 * (icols - 1)) / icols
    IFS, TFS = 23, 25
    pad = 22
    boxes = []
    for inf in infos:
        lines = wrap(F, inf["text"], IFS, bw - 2 * pad - 10)
        hgt = pad + 34 + len(lines) * IFS * 1.36 + pad - 6
        boxes.append((inf, lines, hgt))
    rows_ = [boxes[i:i + icols] for i in range(0, len(boxes), icols)]
    yy = y0
    for rw in rows_:
        rh = max(b[2] for b in rw)
        for k, (inf, lines, _) in enumerate(rw):
            bx_ = x0 + k * (bw + 24)
            col = pal["classes"][inf["class"]]["fill"]
            C.rect(bx_, yy, bw, rh, tint(col, 0.12), rx=14)
            C.rect(bx_, yy, 8, rh, col, rx=4)
            C.reg(bx_, yy, bx_ + bw, yy + rh, f"info {inf['n']}", f"info {inf['n']}")
            r = 17
            marker(C, F, bx_ + pad + 6 + r, yy + pad + 14, r, inf["n"], pal, group=f"info {inf['n']}")
            tx = bx_ + pad + 6 + 2 * r + 12
            ttl = inf["title"]
            if F.width(ttl, TFS) > bw - (tx - bx_) - pad:
                raise SystemExit(f"info title too long: {ttl}")
            C.text(tx, yy + pad + 14 + F.cap(TFS) / 2, ttl, TFS, shade(col))
            for li, ln in enumerate(lines):
                C.text(bx_ + pad + 10, yy + pad + 34 + 26 + li * IFS * 1.36, ln, IFS, ink, weight="regular")
        yy += rh + 20
    return yy - y0 - 20


def finish(C, F, board, V, cfg, W, Ht, out_dir, FS, M):
    # footer
    C.text(W - M, Ht + 30, board.get("footer", "hardcode.tools"), 28, "#90A4AE", anchor="end")
    note = V.get("footer_note", cfg.get("footer_note", ""))
    C.text(M, Ht + 30, note, 20, "#90A4AE", weight="regular")
    C.reg(M, Ht + 8, M + F.width(note, 20, "regular"), Ht + 36, "footer note")
    Ht += 60

    bad = C.check()
    if bad:
        for a, b in bad[:40]:
            print("OVERLAP:", a, "<->", b, file=sys.stderr)
        if not os.environ.get("PINOUT_NOCHECK"):
            raise SystemExit(f"{len(bad)} overlaps")
    for b in C.boxes:
        if b[0] < -0.5 or b[2] > W + 0.5:
            raise SystemExit(f"outside canvas: {b}")

    svg = C.svg(W, Ht)
    base = os.path.join(out_dir, V["output"])
    with open(base + ".svg", "w") as fh:
        fh.write(svg)
    import cairosvg
    target_w = cfg.get("png_width", 2400)
    cairosvg.svg2png(bytestring=svg.encode(), write_to=base + ".png", output_width=target_w,
                     output_height=int(round(Ht * target_w / W)), background_color="white")
    print(f"{os.path.normpath(base)}.png  canvas {W:.0f}x{Ht:.0f} -> {target_w} px wide; chip font {FS * target_w / W:.1f}px")


def pin_by_ref(pins, ref):
    h, n = ref.split(".")
    for p in pins:
        if p["header"] == h and p["pin"] == int(n):
            return p
    raise SystemExit(f"pin {ref} not in pin table")


def chip_label(p):
    if p["type"] == "gnd":
        return "GND"
    return p["silk"]


def chip_class(p):
    return {"power": "power", "gnd": "gnd", "swd": "ctrl", "reset": "ctrl"}.get(p["type"], p["type"] if p["type"] in ("ctrl", "uart", "usb") else "port")


SAMPLES = {"power": "3V3", "gnd": "GND", "ctrl": "RESET", "port": "PTA0", "uart": "UART", "spi": "SPI",
           "i2c": "I2C", "pwm": "PWM", "adc": "ADC", "acmp": "ACMP", "kbi": "KBI", "sys": "CLK", "usb": "USB-C"}


def sample_text(c):
    return SAMPLES.get(c, c.upper())


def marker(C, F, cx, cy, r, n, pal, name=None, group=None, ring=None):
    C.circle(cx, cy, r, pal["ink"], stroke=ring, sw=3 if ring else 0)
    fs = r * 1.15
    C.text(cx, cy + F.cap(fs) / 2, str(n), fs, "#FFFFFF", anchor="middle")
    C.reg(cx - r, cy - r, cx + r, cy + r, name or f"marker {n}", group)


def tint(hexc, a):
    r, g, b = (int(hexc[i:i + 2], 16) for i in (1, 3, 5))
    m = lambda c: int(round(255 - (255 - c) * a))
    return f"#{m(r):02X}{m(g):02X}{m(b):02X}"


def shade(hexc, k=0.75):
    r, g, b = (int(hexc[i:i + 2], 16) for i in (1, 3, 5))
    return f"#{int(r * k):02X}{int(g * k):02X}{int(b * k):02X}"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("board", help="boards/<board>.json")
    ap.add_argument("-v", "--variant", help="variant key (default: all)")
    ap.add_argument("-o", "--out", help="output dir (default from board json, else ./out)")
    ap.add_argument("--palette", default=os.path.join(HERE, "palette.json"))
    a = ap.parse_args()
    pal = json.load(open(a.palette))
    bpath = os.path.abspath(a.board)
    board = json.load(open(bpath))
    bdir = os.path.dirname(bpath)
    out = a.out or os.path.join(bdir, board.get("out_dir", "out"))
    os.makedirs(out, exist_ok=True)
    cfg = dict(pitch=54, bottom_height=640, info_cols=2, png_width=2400)
    cfg.update(board.get("layout", {}))
    for vk in ([a.variant] if a.variant else list(board["variants"])):
        (build_callouts if cfg.get("mode") == "callouts" else build)(board, bdir, vk, pal, out, cfg)


if __name__ == "__main__":
    main()
