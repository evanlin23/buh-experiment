#!/usr/bin/env python3
"""How long must paper be to fold it 12 times?

Britney Gallivan's single-direction folding formula gives the minimum strip length
for n folds of paper of thickness t:   L(n) = (pi * t / 6) * (2^n + 4) * (2^n - 1)

With office paper (t = 0.1 mm):  6 folds 22 cm (fits on A4), 7 folds 88 cm (A4 runs out),
10 folds 55 m (just under the Tower of Pisa), 12 folds 879 m (taller than the Burj Khalifa).
Bonus: the famous "42 folds to the Moon" needs a strip ~107,000 light-years long.

Every length on screen, every landmark crossing and every note is computed from L(n).
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import numpy as np  # noqa: E402
from engine import C, FPS, ease, ease_out, hz, ladder, lerp, run  # noqa: E402
from ladder import LANDMARKS, LogCamera, icon  # noqa: E402

T_PAPER = 1e-4                 # 0.1 mm office paper
LY = 9.4607e15


def L(n):
    return math.pi * T_PAPER / 6 * (2 ** n + 4) * (2 ** n - 1)


def fmt_len(m):
    if m < 0.01:
        return f"{m * 1000:.1f} mm"
    if m < 0.1:
        return f"{m * 100:.1f} cm"
    if m < 1:
        return f"{m * 100:.0f} cm"
    if m < 10:
        return f"{m:.1f} m"
    if m < 1000:
        return f"{m:.0f} m"
    if m < 1e9:
        return f"{m / 1000:,.0f} km"
    if m < 1e12:
        return f"{m / 1e9:.0f} million km"
    if m < 0.1 * LY:
        return f"{m / 1e12:.1f} billion km"
    y = m / LY
    if y < 10:
        return f"{y:.1f} light-years"
    return f"{float(f'{y:.3g}'):,.0f} light-years"


# ------------------------------------------------------------------ timeline
BEAT = 0.5                                                 # 120 BPM
T = {1: -BEAT}                                             # the loop opens on 1 fold already made
T.update({n: BEAT * (n - 2) + (BEAT if n >= 8 else 0) for n in range(2, 13)})  # folds 2-12, one per
#   beat, with one extra beat after fold 7 so "A4 runs out" can be read
T[2] = 1 / FPS          # fold 2 starts on frame 1, so frame 0 is exactly the loop's last frame (1 fold)
T.update({n: 9.25 + BEAT / 4 * (n - 13) for n in range(13, 43)})  # 13-42, sixteenths
DUR = {n: 0.3 if n <= 11 else 0.8 if n == 12 else 0.12 for n in T}
# No hold longer than ~1 s without a new number, headline or sound: a long still
# payoff reads as "the Short is over" and gets swiped.
T_PAY1, T_FACT, T_BONUS, T_PAY2 = 6.5, 7.5, 9.0, 13.25
T_REW, T_REW_END, T_END = 14.25, 16.25, 16.5               # rewind ends on 1 fold = frame 1
TP_LEN = 1219.0                                            # Gallivan's toilet-paper strip (4,000 ft)

BAR_X, GROUND_Y, VIEW_H = 820, 1300, 900
LAD = ladder("D4", 12)          # D-major pentatonic, one rung per fold
LAD_HI = ladder("D5", 10)

BUILD_MARKS = [("rice", 640), ("coin", 730), ("card", 590), ("a4", 150), ("person", 330), ("house", 440),
               ("pisa", 170), ("pyramid", 270), ("eiffel", 470), ("burj", 620)]
COSMIC = [(8849, "Mount Everest", "8,849 m", "mount"), (1e5, "Edge of space", "100 km", "line"),
          (2.02e7, "GPS satellites", "20,200 km up", "star"), (4.0075e7, "Around the Earth", "40,075 km", "planet"), (3.844e8, "The Moon", "384,400 km", "moon"),
          (5.46e10, "Mars at its closest", "55 million km", "planet"), (1.496e11, "The Sun", "150 million km", "sun"), (7.78e11, "Jupiter's orbit", "778 million km", "planet"),
          (4.5e12, "Neptune's orbit", "4.5 billion km", "planet"), (2.5e13, "Voyager 1", "~25 billion km", "star"),
          (LY, "One light-year", "9.5 trillion km", "line"), (4.01e16, "Nearest star", "4.2 light-years", "star"),
          (1344 * LY, "Orion Nebula", "1,344 light-years", "star"), (2.6e4 * LY, "Centre of our galaxy", "26,000 light-years", "star"),
          (9.46e20, "The Milky Way", "100,000 light-years across", "galaxy")]


def rewind_n(t):
    u = (t - T_REW) / (T_REW_END - T_REW)
    return 1 + 41 * (1 - ease(u))


def log_L(nf):
    """log length for fractional fold counts (log-linear between integers)."""
    lo = int(math.floor(nf))
    a = math.log(L(max(lo, 1))) if lo >= 1 else math.log(L(1) / 4)
    b = math.log(L(lo + 1))
    return lerp(a, b, nf - lo)


def state(t):
    """(folds shown on the counter, bar height in metres)."""
    if t >= T_REW:
        nf = rewind_n(t)
        return int(math.ceil(nf - 1e-9)), math.exp(log_L(nf))
    n = max([k for k in T if T[k] <= t], default=0)
    if n == 0:
        return 0, 0.0
    u = ease_out((t - T[n]) / DUR[n])
    a = math.log(L(n - 1)) if n > 1 else math.log(L(1) / 4)
    return n, math.exp(lerp(a, math.log(L(n)), u))


def floor_for(n):
    """Folds 5-7 frame the A4 sheet, for the 'still fits / runs out' beat."""
    return 0.42 if 5 <= n <= 7 else 1e-9


def tp_height(t):
    """Gallivan's real 1.2 km toilet-paper strip rising beside ours during the fact card."""
    if t < T_FACT:
        return 0.0
    return TP_LEN * ease((t - T_FACT) / 0.9)


def ease_inv(y):
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if ease(mid) < y else (lo, mid)
    return lo


def headline_key(t):
    if t < T_PAY1 or t >= T_REW:
        return "hook"
    if t < T_FACT:
        return "pay1"
    if t < T_BONUS:
        return "fact"
    if t < T_PAY2:
        return "bonus"
    return "pay2"


HEADLINES = {
    "hook": ("HOW LONG MUST PAPER BE", "TO FOLD IT 12 TIMES?", 56, 56),
    "pay1": ("TALLER THAN", "THE BURJ KHALIFA", 60, 60),
    "fact": ("A STUDENT DID IT IN 2002", "WITH 1.2 KM OF TOILET PAPER", 54, 46),
    "bonus": ("NOW FOLD IT 42 TIMES", "TO REACH THE MOON", 56, 56),
    "pay2": ("A STRIP AS LONG AS", "THE MILKY WAY IS WIDE", 56, 56),
}


class Scene:
    duration = T_END
    key_times = [0.0, 0.9, 2.1, 2.9, 4.1, 5.1, 6.45, 6.8, 8.2, 9.9, 11.2, 12.4, 13.5, 14.4, 15.2, T_END - 1 / FPS]

    def __init__(self, v):
        self.v = v
        self.tp_pass = T_FACT + 0.9 * ease_inv(L(12) / TP_LEN)
        # fine grid of bar heights for landmark-crossing times (sound and pulses)
        grid = np.arange(0, T_REW, 1 / 600)
        bars = np.array([state(t)[1] for t in grid])
        self.cross = {}
        for kind, _ in BUILD_MARKS:
            h = LANDMARKS[kind]["h"]
            i = np.argmax(bars >= h)
            if bars[i] >= h:
                self.cross[kind] = grid[i]
        for h, name, *_ in COSMIC:
            i = np.argmax(bars >= h)
            if bars[i] >= h:
                self.cross[name] = grid[i]
        # camera track: follows the strip with a short lag (so every fold overshoots and
        # settles), and pushes out slowly through the holds, so the frame is never still
        dt = 1 / 240
        self.cam_t = np.arange(0, T_END + dt, dt)
        logs, cur = [], None
        for t in self.cam_t:
            target = self._target(t)
            cur = target if cur is None else cur + (target - cur) * (1 - math.exp(-dt / 0.16))
            if t > T_END - 0.3:                      # land exactly on frame 1's framing
                cur = lerp(cur, target, ease((t - (T_END - 0.3)) / 0.25))
            logs.append(cur)
        self.cam_log = np.array(logs)

    def _target(self, t):
        n, bar = state(t)
        return math.log(max(bar / 0.72, floor_for(n))) + self._push(t)

    @staticmethod
    def _push(t):
        """Extra log-zoom during holds; continuous, and back to 0 before the loop point."""
        def ramp(t0, t1, amount, back):
            if t < t0:
                return 0.0
            if t < t1:
                return amount * (t - t0) / (t1 - t0)
            return amount * (1 - ease((t - t1) / back))
        return ramp(T_PAY1, T_BONUS, 0.35, 0.5) + ramp(T_PAY2, T_REW, 0.25, 0.6)

    def world_h(self, t, bar):
        lg = float(np.interp(t, self.cam_t, self.cam_log))
        # keep the strip between 55% and 86% of the view: never into the text, never lost
        return min(max(math.exp(lg), bar / 0.86), max(bar / 0.55, floor_for(state(t)[0])))

    # -------------------------------------------------------------- sound
    def audio(self, mix):
        for n in range(1, 13):                      # the fold ladder
            mix.add(T[n], mix.bell(hz(LAD[n - 1])), 0.30)
            mix.add(T[n], mix.sweep(0.2, 3000, 700, 1.0) * np.exp(-mix.t(0.2) * 16), 0.10)
        for kind, _ in BUILD_MARKS:                 # passing a landmark
            if kind in self.cross and kind != "a4":
                mix.add(self.cross[kind], mix.pluck(hz("F#6"), 0.5), 0.10, 0.3)
        mix.add(T_PAY1 - 1.0, mix.sweep(1.0, 300, 7000) * np.linspace(0, 1, 48000) ** 2, 0.08)
        mix.payoff(T_PAY1)
        twinkle = ladder("D6", 8)
        rng = np.random.default_rng(5)
        for i in range(5):                           # sparkle under the payoff tail
            mix.add(T_PAY1 + 0.3 + i * 0.14, mix.grain(hz(twinkle[rng.integers(8)])), 0.08, rng.uniform(-.6, .6))
        mix.add(T_FACT, mix.bell(hz("A5"), 1.2), 0.14, -0.2)
        mix.add(T_FACT, mix.sweep(1.0, 400, 3500, 1.2) * np.linspace(0, 1, 48000), 0.05, 0.4)
        for i in range(8):                           # the toilet-paper strip ticking up
            mix.add(T_FACT + 0.1 + i * 0.11, mix.pluck(hz(ladder("A4", 8)[i]), 0.25, decay=14), 0.08, 0.4)
        mix.add(self.tp_pass, mix.bell(hz("D6"), 1.4), 0.16, 0.3)
        mix.add(T_BONUS, mix.sweep(0.5, 400, 6000) * np.linspace(0, 1, 24000) ** 2, 0.07)
        for i, n in enumerate(range(13, 43)):       # the race to the Milky Way
            mix.add(T[n], mix.pluck(hz(LAD_HI[i % 10]), 0.3), 0.10 + 0.08 * i / 29, (i % 5 - 2) * 0.15)
        for h, name, *_ in COSMIC:
            if name in self.cross:
                mix.add(self.cross[name], mix.bell(hz("A5"), 0.9), 0.16)
        mix.add(T_PAY2 - 0.35, mix.sweep(0.35, 500, 8000) * np.linspace(0, 1, int(0.35 * 48000)) ** 2, 0.08)
        mix.payoff(T_PAY2, chord="D2 A2 D3 F#3 A3 E4 A4", top="A6", gain=1.25)
        mix.add(T_PAY2, mix.pad("D3 A3 D4 F#4 A4", 3.0, attack=0.3, decay=0.6), 0.25)
        for i in range(7):                           # stars of the galaxy twinkling
            mix.add(T_PAY2 + 0.3 + i * 0.1, mix.grain(hz(twinkle[rng.integers(8)]), 0.12), 0.11, rng.uniform(-.7, .7))
        # rewind: one note per fold un-done, falling, with a falling sweep under it
        grid = np.arange(T_REW, T_REW_END, 1 / 1000)
        nf = np.array([rewind_n(t) for t in grid])
        lad_rw = ladder("D3", 22)
        for m in range(41, 0, -1):
            i = np.argmax(nf <= m)
            if nf[i] <= m:
                mix.add(grid[i], mix.pluck(hz(lad_rw[m // 2]), 0.25, decay=14), 0.12)
        mix.add(T_REW, mix.sweep(T_REW_END - T_REW, 8000, 300, 0.6) * np.linspace(1, 0, int((T_REW_END - T_REW) * 48000)), 0.05)
        mix.add(T_REW_END, mix.bell(hz("D3"), 0.5) * np.exp(-mix.t(0.5) * 4), 0.2)

    # -------------------------------------------------------------- picture
    def draw(self, f, t):
        n, bar = state(t)
        cam = LogCamera(ground_y=GROUND_Y, screen_h=VIEW_H)
        cam.set_height(self.world_h(t, bar))
        k = cam.k
        f.line([(60, GROUND_Y), (1020, GROUND_Y)], C["dim"], 3, 0.8)
        self._particles(f, t)
        a_r = (1 - ease((t - T_BONUS) / 0.3)) + ease((t - T_REW) / 0.4) if t >= T_BONUS else 1.0
        self._ruler(f, cam, min(1.0, a_r))

        # landmarks at true size, labels from the same numbers
        for kind, x_px in BUILD_MARKS:
            h = LANDMARKS[kind]["h"]
            r = h / cam.world_h
            a = ease((r - 0.012) / 0.03) * (1 - ease((r - 0.62) / 0.12))
            if a <= 0.01:
                continue
            P = icon(f, kind, cam, (x_px - cam.x0) / k, C["mint"], a, 4)
            tx, ty = P(0, 1.0)
            f.label(LANDMARKS[kind]["label"], LANDMARKS[kind]["sub"], x_px, ty - 62, a=a, px=30)

        # cosmic distance markers for the bonus act
        for h, name, sub, glyph in COSMIC:
            r = h / cam.world_h
            a = ease((r - 0.05) / 0.08) * (1 - ease((r - 0.66) / 0.06))   # appears as the bar passes it
            if a <= 0.01 or t < T_BONUS - 0.2:
                continue
            y = GROUND_Y - h * k
            for x in range(90, BAR_X - 40, 36):
                f.line([(x, y), (x + 18, y)], C["lav"], 3, a * 0.7)
            f.label(name, sub, 90, y - 62, a=a, px=30, sub_color=C["lav"])
            gx = 640
            if glyph == "moon":
                f.circle(gx, y, 18, C["white"], 3, a)
            elif glyph == "sun":
                f.circle(gx, y, 30, C["warm"], 4, a, fill=0.25)
            elif glyph == "planet":
                f.circle(gx, y, 16, C["sky"], 3, a)
            elif glyph == "star":
                f.dot(gx, y, 7, C["white"], a)
            elif glyph == "mount":
                f.line([(gx - 40, y + 30), (gx, y), (gx + 40, y + 30)], C["mint"], 3, a)
            elif glyph == "galaxy":
                self._galaxy(f, 390, y + 150, 230, a, t)

        # the strip of paper, stood on end
        bar_px = bar * k
        if bar_px > 0:
            pulse = 0.0
            for m, tm in T.items():
                if 0 <= t - tm < 0.25:
                    pulse = max(pulse, 1 - (t - tm) / 0.25)
            w = 18 + 10 * pulse
            f.line([(BAR_X, GROUND_Y), (BAR_X, GROUND_Y - max(bar_px, 1.5))], C["warm"], w)
            f.dot(BAR_X, GROUND_Y - bar_px, 6 + 6 * pulse, C["core"], 0.9)

        # the real record: 1.2 km of toilet paper rising beside the 879 m strip
        a_tp = 1 - ease((t - T_BONUS) / 0.3) if t >= T_FACT else 0.0
        h_tp = tp_height(t) * k
        if a_tp > 0 and h_tp > 0:
            x_tp = BAR_X + 120
            f.line([(x_tp, GROUND_Y), (x_tp, GROUND_Y - h_tp)], C["pink"], 14, a_tp)
            f.label("Toilet paper", "1.2 km", x_tp, GROUND_Y - h_tp - 66, a=a_tp, px=28, anchor="mm", sub_color=C["pink"])

        # payoff flashes
        for tp, s in ((T_PAY1, 1.0), (T_PAY2, 1.4)):
            if 0 <= t - tp < 1.5:
                f.flash = max(f.flash, s * math.exp(-(t - tp) * 3.5))
                v = (t - tp) / 1.0
                if v < 1:
                    rr = 40 + 520 * v
                    f.circle(BAR_X, GROUND_Y - bar_px, rr, C["lav"], 3, 0.8 * (1 - v))

        # headline with short crossfades between states
        key = headline_key(t)
        b = max([x for x in (T_PAY1, T_FACT, T_BONUS, T_PAY2, T_REW) if x <= t], default=None)
        if b is not None and t - b < 0.2:
            u = (t - b) / 0.2
            self._head(f, headline_key(b - 1e-6), 1 - u)
            self._head(f, key, u)
        else:
            self._head(f, key, 1.0)

        # counter and the A4 callouts
        if n > 0:
            f.text(f"{n} FOLD{'S' if n != 1 else ''}", 540, 300, 66, C["white"], "Bold")
            f.text(f"needs {fmt_len(L(n))} of paper", 540, 384, 44, C["mint"], "Bold")
        if T[6] <= t < T[7]:
            f.text("STILL FITS ON A4", 540, 452, 36, C["lav"], "ExtraBold", a=min(1, (t - T[6]) * 8))
        elif T[7] <= t < T[8]:
            f.text("A4 RUNS OUT: THE 7-FOLD LIMIT", 540, 452, 36, C["lav"], "ExtraBold", a=min(1, (t - T[7]) * 6))

    @staticmethod
    def _ruler(f, cam, a):
        """A 1-2-5 log ruler up the left edge; its ticks slide as the camera zooms."""
        if a <= 0:
            return
        e0 = math.floor(math.log10(cam.world_h)) - 2
        for e in range(e0, e0 + 4):
            for m in (1, 2, 5):
                v = m * 10.0 ** e
                if v < 1e-4:
                    continue
                y = GROUND_Y - v * cam.k
                if 520 < y < GROUND_Y - 4:
                    big = m == 1
                    f.line([(44, y), (66 if big else 58, y)], C["dim"], 3 if big else 2, a * (0.9 if big else 0.5))
                    if big:
                        f.text(fmt_len(v).replace(".0 ", " "), 74, y, 22, C["dim"], "SemiBold", anchor="lm", a=a * 0.9)
        f.line([(44, 520), (44, GROUND_Y)], C["dim"], 2, a * 0.35)

    @staticmethod
    def _particles(f, t):
        """Faint drifting motes. Each moves exactly one screen height per loop, and twinkles
        at a whole number of cycles per loop, so the last frame still matches the first."""
        rng = np.random.default_rng(11)
        for i in range(34):
            x0, y0 = rng.uniform(40, 1040), rng.uniform(0, 1920)
            cyc, ph, r = rng.integers(1, 4), rng.uniform(0, 6.28), rng.uniform(1.6, 3.2)
            y = (y0 - 1920 * t / T_END) % 1920
            x = x0 + 12 * math.sin(2 * math.pi * t / T_END + ph)
            a = 0.18 + 0.17 * math.sin(2 * math.pi * cyc * t / T_END + ph)
            f.dot(x, y, r, C["lav"] if i % 3 else C["core"], a)

    def _head(self, f, key, a):
        l1, l2, p1, p2 = HEADLINES[key]
        f.text(l1, 540, 118, p1, C["white"], a=a)
        f.text(l2, 540, 118 + p1 * 1.2, p2, C["lav"], a=a)

    @staticmethod
    def _galaxy(f, cx, cy, R, a, t):
        rng = np.random.default_rng(3)
        spin = (t - T_PAY2) * 0.25
        for arm in range(2):
            for i in range(70):
                th = i / 70 * 3.2 * math.pi + arm * math.pi + spin
                rr = R * (0.08 + 0.92 * i / 70)
                x = cx + rr * math.cos(th) + rng.normal(0, 6)
                y = cy + 0.42 * rr * math.sin(th) + rng.normal(0, 4)
                f.dot(x, y, 2.2 + 2.5 * (1 - i / 70), C["core"] if i < 12 else C["lav"], a * (0.9 - 0.5 * i / 70))
        f.dot(cx, cy, 14, C["core"], a)


if __name__ == "__main__":
    run(Scene)
