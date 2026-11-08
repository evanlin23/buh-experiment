"""RevealShort: a simple random rule, repeated a million times, reveals a shape.

The third format: no bar, no ramps. A glowing point cloud built from the real iterations of a
rule (a chaos game on a polygon, or an affine 'IFS' like the Barnsley fern). The count doubles
on every beat; the first few jumps are drawn one by one so the rule is visible; every early
jump is a pluck panned to where it lands, later beats are a shimmer sampled from real landings.

Acts (fixed order): build -> payoff -> bonus variants (optional) -> rewind (halving) -> frame 0.
"""
import math

import numpy as np
from scipy.ndimage import gaussian_filter

from engine import C, FPS, ease, font, hz, ladder

SAFE_W = 960
CX, CY, R = 540, 960, 455


def polygon(k, radius=R, rot=-90.0):
    a = np.deg2rad(rot + 360.0 * np.arange(k) / k)
    return np.stack([CX + radius * np.cos(a), CY + radius * np.sin(a)], 1)


def run_rule(rule, n, rng):
    """Iterate a rule n times. Returns points (n+1, 2) in design px, chosen-target index per jump,
    and the target points (polygon rules) or None (IFS)."""
    if rule["type"] == "polygon":
        k = rule["corners"]
        t = polygon(k, rule.get("radius", 1.0) * R, rule.get("rot", -90.0 if k != 4 else -45.0))
        if rule.get("center"):
            t = np.vstack([t, [[CX, CY]]])
        kk = len(t)
        idx = (np.cumsum(rng.integers(1, kk, n)) % kk) if rule.get("norepeat") else rng.integers(0, kk, n)
        r = rule.get("ratio", 0.5)
        tx, ty = t[idx, 0].tolist(), t[idx, 1].tolist()
        x, y = float(t[0, 0]), float(t[0, 1])
        xs, ys = [x], [y]
        for i in range(n):
            x += r * (tx[i] - x)
            y += r * (ty[i] - y)
            xs.append(x)
            ys.append(y)
        return np.array([xs, ys]).T, np.concatenate([[0], idx]), t
    # IFS: maps [a, b, c, d, e, f, p] with x' = a x + b y + e, y' = c x + d y + f
    maps = np.array(rule["maps"], float)
    p = maps[:, 6] / maps[:, 6].sum()
    idx = rng.choice(len(maps), n, p=p)
    m = maps[idx].tolist()
    x, y = 0.0, 0.0
    xs, ys = [x], [y]
    for a, b, c, d, e, f, _ in m:
        x, y = a * x + b * y + e, c * x + d * y + f
        xs.append(x)
        ys.append(y)
    P = np.array([xs, ys]).T
    lo, hi = np.percentile(P[50:], 0.2, axis=0), np.percentile(P[50:], 99.8, axis=0)
    sc = min(860 / (hi[0] - lo[0]), 880 / (hi[1] - lo[1]))
    mid = (lo + hi) / 2
    # y is up in IFS space; centre a little high so the shape clears the caption area and the handle
    out = np.stack([CX + (P[:, 0] - mid[0]) * sc, CY - 70 - (P[:, 1] - mid[1]) * sc], 1)
    return out, np.concatenate([[0], idx]), None


class RevealShort:
    def __init__(self, v, spec):
        self.v, self.spec, self.S = v, spec, v.S
        self.beat = 60.0 / spec.get("bpm", 120)
        rng = np.random.default_rng(spec.get("seed", 20261108))
        self.nb = spec.get("doublings", 20)
        self.color = C[spec.get("color", "pink")]
        self.main = self._shape(run_rule(spec["rule"], 2 ** self.nb, rng))
        self.bonus = [dict(b, shape=self._shape(run_rule(b["rule"], 2 ** 18, rng))) for b in spec.get("bonus", [])]
        self._timeline()
        self.key_times = self._key_times()

    def _shape(self, res):
        pts, idx, targets = res
        W, H, S = self.v.W, self.v.H, self.S
        ix = np.clip((pts[:, 0] * S).astype(np.int64), 0, W - 1)
        iy = np.clip((pts[:, 1] * S).astype(np.int64), 0, H - 1)
        return dict(pts=pts, idx=idx, targets=targets, flat=iy * W + ix)

    # ---------------------------------------------------------------- timeline
    def _timeline(self):
        b = self.beat
        n = 2 ** self.nb + 1
        self.TS, self.TA = np.full(n, -1.0), np.full(n, -1.0)
        for k in range(self.nb + 1):
            lo, hi = (1, 1) if k == 0 else (2 ** (k - 1) + 1, 2 ** k)
            m = hi - lo + 1
            st = k * b + np.arange(m) / m * 0.8 * b
            d = min(0.3, 0.8 * b / m) if m <= 8 else 0.0
            self.TS[lo:hi + 1], self.TA[lo:hi + 1] = st, st + d
        self.T_PAY = (self.nb + 1) * b
        self.T_BONUS = self.T_PAY + self.spec.get("payoff_beats", 2) * b
        self.BONUS_LEN = 2 * b
        self.T_BACK = self.T_BONUS + len(self.bonus) * self.BONUS_LEN
        self.T_REW = self.T_BACK + 6 / FPS
        self.STEP = 5 / FPS
        self.T_REW_END = self.T_REW + (self.nb + 1) * self.STEP
        self.duration = round((self.T_REW_END + 0.5 * b) * FPS) / FPS

    def rewind_count(self, t):
        s = int(math.floor((t - self.T_REW) / self.STEP + 1e-9))
        return 2 ** self.nb if s < 0 else (2 ** (self.nb - 1 - s) if s <= self.nb - 1 else 0)

    def count(self, t):
        if t < self.T_PAY:
            return int(np.searchsorted(self.TA, t, side="right")) - 1
        if t < self.T_REW:
            return 2 ** self.nb
        return self.rewind_count(t)

    # ---------------------------------------------------------------- picture
    def angle(self, t):
        """Spin by the main shape's own symmetry angle over the whole loop, so the last frame
        is the first frame again (a triangle turns exactly 120 degrees)."""
        r = self.spec["rule"]
        if r["type"] != "polygon":                   # IFS shapes sway gently about their base, like a plant in wind
            cyc = max(1, round(self.duration / 4))
            return self.spec.get("sway", 0.07) * math.sin(2 * math.pi * cyc * t / self.duration)
        if not self.spec.get("spin", True):
            return 0.0
        return 2 * math.pi / r["corners"] * t / self.duration

    @property
    def pivot(self):
        return (CX, CY) if self.spec["rule"]["type"] == "polygon" else tuple(self.main["pts"][0])

    def rot(self, p, th):
        if th == 0:
            return p
        c, s_ = math.cos(th), math.sin(th)
        px, py = self.pivot
        x, y = p[0] - px, p[1] - py
        return (px + c * x - s_ * y, py + s_ * x + c * y)

    def density(self, shape, n, th=0.0):
        W, H, S = self.v.W, self.v.H, self.S
        if th:
            P = shape["pts"][:n + 1]
            c, s_ = math.cos(th), math.sin(th)
            px, py = self.pivot
            x, y = P[:, 0] - px, P[:, 1] - py
            ix = np.clip(((px + c * x - s_ * y) * S).astype(np.int64), 0, W - 1)
            iy = np.clip(((py + s_ * x + c * y) * S).astype(np.int64), 0, H - 1)
            flat = iy * W + ix
        else:
            flat = shape["flat"][:n + 1]
        D = np.bincount(flat, minlength=H * W).astype(np.float32).reshape(H, W)
        sig = float(np.interp(math.log2(n + 1), [0, 6, 12, 20], [5.0, 3.2, 1.4, 0.7])) * self.S
        if sig >= 0.35:
            D = gaussian_filter(D, sig) * (2 * math.pi * sig * sig)
        occ = D[D > 0.05]
        ref = max(float(occ.mean()) if occ.size else 1.0, 0.8)
        return 1 - np.exp(-D * (1.15 / ref))

    def _fit(self, s, target):
        w = font("ExtraBold", target).getlength(s)
        return target if w <= SAFE_W else max(28, int(target * SAFE_W / w))

    def _head(self, f, lines, a=1.0, y=118):
        l1, l2 = lines
        p = min(self._fit(l1, 58), self._fit(l2, 58))
        f.text(l1, 540, y, p, C["white"], a=a)
        f.text(l2, 540, y + p * 1.2, p, C["lav"], a=a)

    def draw_cover(self, f, t, headline="hook"):
        self.draw(f, t, force_head=True)

    def draw(self, f, t, force_head=False):
        b = self.beat
        layers, marks = [], []
        if t < self.T_PAY:
            n = self.count(t)
            layers.append((self.main, n, 1.0))
            marks.append((self.main, 1.0))
        elif t < self.T_BONUS:
            layers.append((self.main, 2 ** self.nb, 1.0))
            marks.append((self.main, 1.0))
        elif t < self.T_REW:
            if t < self.T_BACK:
                i = int((t - self.T_BONUS) / self.BONUS_LEN)
                t0 = self.T_BONUS + i * self.BONUS_LEN
                prev = self.main if i == 0 else self.bonus[i - 1]["shape"]
                cur = self.bonus[i]["shape"]
                w = min(1.0, (t - t0) / 0.2)
                ncur = int(2 ** (10 + 8 * min(1.0, (t - t0) / 0.6)))
            else:
                prev, cur = (self.bonus[-1]["shape"] if self.bonus else self.main), self.main
                w, ncur = min(1.0, (t - self.T_BACK) / (self.T_REW - self.T_BACK)), 2 ** self.nb
            pn = 2 ** self.nb if prev is self.main else 2 ** 18
            if w < 1:
                layers.append((prev, pn, 1 - w))
                marks.append((prev, 1 - w))
            layers.append((cur, ncur, w))
            marks.append((cur, w))
        else:
            layers.append((self.main, self.rewind_count(t), 1.0))
            marks.append((self.main, 1.0))
        th = self.angle(t)
        I = sum(self.density(sh, n, th) * wt for sh, n, wt in layers)
        # a wave of light sweeping across the shape, a whole number of times per loop
        if not hasattr(self, "_grid"):
            yy, xx = np.mgrid[0:self.v.H, 0:self.v.W].astype(np.float32)
            self._grid = (xx * 0.6 + yy * 0.8) / (self.S * 190.0)
        cyc = max(1, round(self.duration / 2.2))
        I = I * (0.7 + 0.3 * (0.5 + 0.5 * np.cos(2 * math.pi * cyc * t / self.duration - self._grid)))
        f.intensity(I * 0.95, self.color)
        self._particles(f, t)

        # target markers (polygon rules)
        for sh, wt in marks:
            if sh["targets"] is not None:
                for x, y in (self.rot(q, th) for q in sh["targets"]):
                    f.circle(x, y, 15, C["lav"], 3, 0.8 * wt)
                    f.dot(x, y, 3.5, C["white"], 0.9 * wt)
        # the first jumps, drawn one by one
        if t < self.T_PAY:
            pts, idx, tg = self.main["pts"], self.main["idx"], self.main["targets"]
            n = self.count(t)
            p_hi = int(np.searchsorted(self.TS, t, side="right"))
            for p in range(n + 1, min(p_hi, 40)):
                u = (t - self.TS[p]) / max(1e-6, self.TA[p] - self.TS[p])
                e = 1 - (1 - u) ** 3
                (x0, y0), (x1, y1) = (self.rot(q, th) for q in (pts[p - 1], pts[p]))
                if tg is not None:                       # polygon rules: show the corner being aimed at
                    cx, cy = self.rot(tg[idx[p]], th)
                    f.line([(x0, y0), (cx, cy)], C["lav"], 2, 0.3 * min(1, u * 6))
                xe, ye = x0 + (x1 - x0) * e, y0 + (y1 - y0) * e
                f.line([(x0, y0), (xe, ye)], C["core"], 4, 0.8 * min(1, u * 6))
                f.dot(xe, ye, 7, C["core"], min(1, u * 6))
            for p in range(1, 33):                       # a pulse where each early jump lands (or aims)
                v = (t - self.TS[p]) / 0.4
                if 0 <= v < 1:
                    cx, cy = self.rot(tg[idx[p]] if tg is not None else pts[p], th)
                    if tg is not None:
                        f.circle(cx, cy, 16 + 46 * v, C["lav"], 4, (1 - v) * min(1, v * 8))
                    else:                                # IFS: no corners, so make each landing itself visible
                        f.circle(cx, cy, 16 + 130 * v, C["lav"], 5, (1 - v) * min(1, v * 8))
                        f.flash = max(f.flash, 0.18 * (1 - v))
        # start ring on frame 1, payoff flash + ring
        if 0 < t < 0.5:
            sx, sy = self.rot(self.main["pts"][0], th)
            f.circle(sx, sy, 16 + 220 * t / 0.5, C["white"], 5, 0.9 * (1 - t / 0.5))
            f.flash = max(f.flash, 0.3 * (1 - t / 0.5))
        if 0 <= t - self.T_PAY < 1.2:
            f.flash = math.exp(-(t - self.T_PAY) * 4)
            vv = (t - self.T_PAY) / 1.2
            f.circle(CX, CY, 60 + 440 * vv, C["lav"], 3, 0.8 * (1 - vv))
        for i in range(len(self.bonus)):
            t0 = self.T_BONUS + i * self.BONUS_LEN
            if 0 <= t - t0 < 0.4:
                f.flash = max(f.flash, 0.5 * (1 - (t - t0) / 0.4))

        # text
        hook = self.spec["hook"]
        hook_beats = self.spec.get("hook_beats", 5)
        if force_head:
            self._head(f, hook)
            return
        if t < self.T_PAY:
            kb = min(int(t / b), self.nb)
            if kb < hook_beats:
                self._head(f, hook)
            else:
                a = min(1.0, (t - hook_beats * b) / (4 / FPS))
                if a < 1:
                    self._head(f, hook, 1 - a)
                f.counter(self.spec.get("counter_label", "JUMPS"), f"{2 ** kb:,}", a=a)
        elif t < self.T_BONUS:
            self._head(f, self.spec["answer"], y=150)
        elif t < self.T_BACK:
            i = int((t - self.T_BONUS) / self.BONUS_LEN)
            self._head(f, self.bonus[i]["lines"], y=150)
        elif t < self.T_REW:
            f.counter(self.spec.get("counter_label", "JUMPS"), f"{2 ** self.nb:,}")
        else:
            n = self.rewind_count(t)
            w = min(1.0, max(0.0, (t - (self.T_REW_END - 0.4)) / 0.4))
            if w < 1:
                f.counter(self.spec.get("counter_label", "JUMPS"), f"{n:,}", a=1 - w)
            if w > 0:
                self._head(f, hook, w)

    def _particles(self, f, t):
        rng = np.random.default_rng(31)
        T_END = self.duration
        for i in range(26):
            x0, y0 = rng.uniform(40, 1040), rng.uniform(0, 1920)
            cyc, ph, r = rng.integers(1, 4), rng.uniform(0, 6.28), rng.uniform(1.5, 2.8)
            x = (x0 + 1080 * t / T_END) % 1080              # drifts sideways in this format
            y = y0 + 14 * math.sin(2 * math.pi * t / T_END + ph)
            f.dot(x, y, r, C["lav"], 0.14 + 0.12 * math.sin(2 * math.pi * cyc * t / T_END + ph))

    # ---------------------------------------------------------------- sound
    def audio(self, mix):
        rng = np.random.default_rng(4)
        b = self.beat
        lad = ladder(self.spec.get("ladder", "A2"), self.nb + 1)
        sparkle = ladder("D5", 10)
        pts, idx = self.main["pts"], self.main["idx"]
        ys = pts[:, 1]
        corner_notes = ladder("D5", 8)

        def pan_of(x):
            return float(np.clip((x - CX) / R * 0.75, -0.9, 0.9))

        def pitch_of(y):
            k = int((1 - (y - ys.min()) / (ys.max() - ys.min() + 1e-9)) * (len(sparkle) - 0.01))
            return hz(sparkle[k])
        mix.add(1 / FPS, mix.tick(3000), 0.12)
        for k in range(self.nb + 1):
            mix.add(k * b, mix.bell(hz(lad[k])), 0.28)
            m = 1 if k == 0 else 2 ** (k - 1)
            lo = 1 if k == 0 else 2 ** (k - 1) + 1
            if m <= 32:
                for p in range(lo, 2 ** k + 1):
                    mix.add(self.TA[p], mix.pluck(hz(corner_notes[int(idx[p]) % 8])), 0.22 * m ** -0.42, pan_of(pts[p, 0]))
            else:
                g = int(min(140, 14 + 10 * (k - 6)))
                for p in rng.choice(np.arange(lo, 2 ** k + 1), g, replace=False):
                    mix.add(self.TA[p], mix.grain(pitch_of(pts[p, 1])), 0.05, pan_of(pts[p, 0]))
        mix.add(self.T_PAY - 3 * b, mix.sweep(3 * b, 300, 9000) * np.linspace(0, 1, int(3 * b * 48000)) ** 2, 0.09)
        mix.payoff(self.T_PAY)
        for j in range(5):
            mix.add(self.T_PAY + 0.3 + j * 0.14, mix.grain(hz(ladder("D6", 8)[rng.integers(8)]), 0.12), 0.08, rng.uniform(-.7, .7))
        for i, bo in enumerate(self.bonus):
            t0 = self.T_BONUS + i * self.BONUS_LEN
            mix.add(t0, mix.pad(bo.get("chord", "B2 F#3 B3 D4 F#4"), 1.6, decay=1.6), 0.42)
            sp = bo["shape"]["pts"]
            for j in range(50):
                p = rng.integers(1, len(sp))
                mix.add(t0 + 0.6 * j / 50, mix.grain(pitch_of(sp[p, 1])), 0.05, pan_of(sp[p, 0]))
            mix.add(t0 + b, mix.pluck(hz("D6"), 0.3), 0.1)
        for s in range(self.nb + 1):
            mix.add(self.T_REW + s * self.STEP, mix.pluck(hz(lad[self.nb - s]), 0.3), 0.2)
        d = self.T_REW_END - self.T_BACK
        mix.add(self.T_BACK, mix.sweep(d, 9000, 300, 0.6) * np.linspace(1, 0, int(d * 48000)), 0.06)
        mix.add(self.T_REW_END, mix.bell(hz("D3"), 0.5) * np.exp(-mix.t(0.5) * 4), 0.22)

    def _key_times(self):
        b = self.beat
        ts = [0.0, 0.15, 1.3, 2.3, 3.2, 5.6, self.T_PAY - 0.3, self.T_PAY + 0.25]
        ts += [self.T_BONUS + i * self.BONUS_LEN + 0.6 for i in range(len(self.bonus))]
        ts += [self.T_REW + 0.8, self.duration - 1 / FPS]
        return sorted(set(round(x, 2) for x in ts if 0 <= x < self.duration))
