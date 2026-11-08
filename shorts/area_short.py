"""AreaShort: a sheet doubles in area, again and again, until it covers something enormous.

The fourth format. It reuses the ladder's timeline, acts and sound (with a paper-slap on every
doubling), but the picture is 2-D tiling: the sheet grows by gaining a copy beside it, the cut
line between the halves stays, so the nested halvings build up the classic A-size diagram.
Landmarks are true-size rectangles anchored at the same corner. A scale bar replaces the ruler.
"""
import math

import numpy as np

from engine import C, ease, ease_out, lerp
from ladder_short import LadderShort

CXS, CYS = 540, 990            # screen centre of the drawing area
BOX_W, BOX_H = 860, 760        # drawing area


class AreaShort(LadderShort):
    def __init__(self, v, spec):
        sh = spec["sheet"]
        self.w0, self.h0 = sh["w"], sh["h"]
        sp = dict(spec)
        sp["unit"] = "area"
        sp["quantity"] = {"formula": f"{self.w0 * self.h0!r} * 2**n"}
        sp.setdefault("marks", [])
        sp["marks"] = [dict(m, q=m["w"] * m["h"] if "w" in m else m["area"]) for m in spec.get("marks", [])]
        n_max = max(a.get("to", 0) for a in spec["acts"])
        self._dims = [(self.w0, self.h0)]
        for _ in range(n_max + 1):
            w, h = self._dims[-1]
            self._dims.append((2 * w, h) if w <= h else (w, 2 * h))   # double the short side
        super().__init__(v, sp)
        for ms, m in zip(sp["marks"], self.markers):    # keep true rectangle sizes for drawing
            if "w" in ms:
                m["w"], m["h"] = ms["w"], ms["h"]

    # ---------------------------------------------------------------- geometry
    def dims(self, n):
        return self._dims[max(0, min(len(self._dims) - 1, n))]

    def frame_geom(self, t):
        """(sheet w, sheet h, newly added half rect or None, pixels per metre, camera centre)."""
        if t >= self.rewind["t0"]:
            nf = self.rewind_n(t)
            lo = int(math.floor(nf))
            u = nf - lo
            (w0, h0), (w1, h1) = self.dims(lo), self.dims(lo + 1)
            w, h = (lerp(w0, w1, u), lerp(h0, h1, u))
            new = None
            ref = (math.exp(lerp(math.log(w0), math.log(w1), u)), math.exp(lerp(math.log(h0), math.log(h1), u)))
        else:
            n = max(k for k, tk in self.T.items() if tk <= t)
            u = 1.0 if n == self.start else ease_out((t - self.T[n]) / self.DUR[n])
            (w0, h0), (w1, h1) = self.dims(n - 1) if n > self.start else self.dims(n), self.dims(n)
            if n == self.start:
                w, h, new = w1, h1, None
            elif w1 > w0:
                w, h = w0 + (w1 - w0) * u, h1
                new = (w0, 0, w, h1)
            else:
                w, h = w1, h0 + (h1 - h0) * u
                new = (0, h0, w1, h)
            uc = ease(min(1.0, (t - self.T[n]) / max(self.DUR[n], 0.12))) if n > self.start else 1.0
            ref = (math.exp(lerp(math.log(w0), math.log(w1), uc)), math.exp(lerp(math.log(h0), math.log(h1), uc)))
        push = math.exp(self._push(t))
        k = min(BOX_W * 0.82 / ref[0], BOX_H * 0.82 / ref[1]) / push
        return w, h, new, k, (ref[0] / 2, ref[1] / 2)

    # ---------------------------------------------------------------- picture
    def draw(self, f, t, force_headline=None):
        n, q = self.state(t)
        act = self.act_at(t)
        w, h, new, k, (cx, cy) = self.frame_geom(t)
        S = lambda x, y: (CXS + (x - cx) * k, CYS - (y - cy) * k)  # noqa: E731   world (m, y up) -> screen
        self._particles(f, t)

        # landmarks: true-size rectangles (or equal-area squares), anchored at the sheet's corner
        for m in self.icons + self.markers:
            if "w" in m:
                mw, mh = m["w"], m["h"]
            else:
                mw = mh = math.sqrt(m["q"])
            size = max(mw * k / BOX_W, mh * k / BOX_H)
            a = ease((size - 0.04) / 0.06) * (1 - ease((size - 1.0) / 0.15))
            if a <= 0.01:
                continue
            col = C["mint"] if "w" in m else C["sky"]
            corners = [S(0, 0), S(mw, 0), S(mw, mh), S(0, mh), S(0, 0)]
            for (x0, y0), (x1, y1) in zip(corners, corners[1:]):
                L = math.hypot(x1 - x0, y1 - y0)
                steps = max(1, int(L / 26))
                for i in range(0, steps, 2):              # dashed outline
                    u0, u1 = i / steps, min(1, (i + 1) / steps)
                    f.line([(lerp(x0, x1, u0), lerp(y0, y1, u0)), (lerp(x0, x1, u1), lerp(y0, y1, u1))], col, 3, a * 0.9)
            lx, ly = S(0, mh)
            f.label(m["label"], m["sub"], max(70, lx + 10), ly - 46, a=a, px=28, sub_color=col)

        # the sheet: outline, faint fill, the newly added half flashing, nested cut lines
        x0, y0 = S(0, 0)
        x1, y1 = S(w, h)
        f.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], C["core"], 4, 0.95, fill=0.07)
        if new:
            u = (t - self.T[n]) / max(1e-6, self.DUR[n])
            nx0, ny0 = S(new[0], new[1])
            nx1, ny1 = S(new[2], new[3])
            f.poly([(nx0, ny0), (nx1, ny0), (nx1, ny1), (nx0, ny1)], C["warm"], 0, 1.0, fill=0.35 * max(0.0, 1 - u))
        top = n if t < self.rewind["t0"] else int(math.ceil(self.rewind_n(t)))
        for lvl in range(max(self.start + 1, top - 22), top + 1):
            pw, ph = self.dims(lvl - 1)
            cw, ch = self.dims(lvl)
            if lvl == top and new:                   # the cut that's forming right now
                pass
            if cw > pw:
                seg = [S(pw, 0), S(pw, ph)]
            else:
                seg = [S(0, ph), S(pw, ph)]
            L = math.hypot(seg[1][0] - seg[0][0], seg[1][1] - seg[0][1])
            if L < 5:
                continue
            f.line(seg, C["lav"], 3 if L > 60 else 2, min(0.8, L / 160))
        ax, ay = S(self.w0, self.h0)
        if abs(ax - x0) > 3:                          # the original A4 sheet, highlighted
            f.poly([(x0, y0), (ax, y0), (ax, ay), (x0, ay)], C["warm"], 3, 0.9, fill=0.25)

        # scale bar (1-2-5 steps) instead of the ladder's ruler
        target_px = 180
        raw = target_px / k
        e = math.floor(math.log10(raw))
        val = min((m * 10 ** e for m in (1, 2, 5, 10)), key=lambda v: abs(v * k - target_px))
        bx0, by = 110, 1440
        f.line([(bx0, by), (bx0 + val * k, by)], C["dim"], 4, 0.9)
        f.line([(bx0, by - 10), (bx0, by + 10)], C["dim"], 3, 0.9)
        f.line([(bx0 + val * k, by - 10), (bx0 + val * k, by + 10)], C["dim"], 3, 0.9)
        f.text(self._len(val), bx0 + val * k + 16, by, 26, C["dim"], "SemiBold", anchor="lm")

        # payoff flash + ring, card pulses
        for a in self.acts:
            if a["type"] == "payoff" and 0 <= t - a["t0"] < 1.5:
                s = 1.4 if a.get("size") == "big" else 1.0
                f.flash = max(f.flash, s * math.exp(-(t - a["t0"]) * 3.5))
                v = (t - a["t0"]) / 1.0
                if v < 1:
                    f.circle(CXS, CYS, 60 + 520 * v, C["lav"], 3, 0.8 * (1 - v))
            if a["type"] == "card" and a["t0"] <= t < a["t1"]:
                v = ((t - a["t0"]) % self.beat) / self.beat
                f.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], C["mint"], 3 + 4 * (1 - v), 0.6 * (1 - v))

        # text (headline, counter, callouts) as in the ladder
        if force_headline:
            self._draw_head(f, force_headline)
        else:
            cur = self._headline(act) or self._last_headline(act)
            i = self.acts.index(act)
            prev = (self._headline(self.acts[i - 1]) or self._last_headline(self.acts[i - 1])) if i else cur
            u = (t - act["t0"]) / 0.2
            if u < 1 and prev != cur:
                self._draw_head(f, prev, 1 - u)
                self._draw_head(f, cur, u)
            else:
                self._draw_head(f, cur)
        l1, l2 = self.counter_text(n)
        f.text(l1, 540, 300, min(66, self._fit(l1, 66)), C["white"], "Bold")
        f.text(l2, 540, 384, min(44, self._fit(l2, 44)), C["mint"], "Bold")
        if act["type"] == "climb":
            for step, text in act.get("callouts", {}).items():
                s_ = int(step)
                nxt = min([tm for mm, tm in self.T.items() if mm > s_], default=act["t1"])
                if self.T.get(s_, 1e9) <= t < nxt:
                    f.text(text, 540, 452, min(36, self._fit(text, 36)), C["lav"], "ExtraBold", a=min(1, (t - self.T[s_]) * 8))

    @staticmethod
    def _len(m):
        if m < 1:
            return f"{m * 100:.0f} cm"
        if m < 1000:
            return f"{m:.0f} m"
        return f"{m / 1000:,.0f} km"
