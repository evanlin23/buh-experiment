"""LadderShort: the data-driven scale-ladder template.

A Short is a JSON spec (see shorts/specs/ and docs/PIPELINE.md):
  * a quantity q(n) (formula or list), a unit (length / count / time / mass),
  * an ordered list of acts:
      climb   - steps n -> n+1 ... on the beat; optional headline, callouts, pauses
      payoff  - the answer replaces the headline; flash, ring, chord
      card    - a fact card; optional comparison bar rising beside the main bar
      rewind  - runs the count back to the first frame, so the Short loops
  * marks: true-size icons (length unit only) or labelled markers, passed as the bar grows.

Everything on screen and every sound is derived from those numbers, so labels cannot
lag their drawings and every note lands on its event. House rules are built in:
motion on frame 1, no hold without motion or sound, the last frame equals the first.
"""
import math

import numpy as np

import units
from engine import C, FPS, ease, ease_out, font, hz, ladder, lerp
from ladder import LANDMARKS, LogCamera, icon

BAR_X, GROUND_Y, VIEW_H = 820, 1300, 900
SAFE_W = 960


def _eval(expr, n, params):
    env = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
    env.update(params)
    env["n"] = n
    return float(eval(expr, {"__builtins__": {}}, env))  # specs are our own trusted files


class LadderShort:
    def __init__(self, v, spec):
        self.v, self.spec = v, spec
        self.unit = spec.get("unit", "length")
        self.fmt = units.FORMAT[spec.get("format", self.unit)]
        self.beat = 60.0 / spec.get("bpm", 120)
        qs = spec["quantity"]
        self._q_list = qs.get("values")
        self._q_expr, self._q_params = qs.get("formula"), qs.get("params", {})
        self.start = spec.get("start", 1)
        self._build_timeline()
        self._build_marks()
        self._build_camera()
        self.key_times = self._key_times()

    # ---------------------------------------------------------------- quantity
    def q(self, n):
        if self._q_list is not None:
            return float(self._q_list[int(n) - self.start])
        return _eval(self._q_expr, n, self._q_params)

    def log_q(self, nf):
        lo = int(math.floor(nf))
        if lo >= self.n_max:
            return math.log(self.q(self.n_max))
        a = math.log(self.q(max(lo, self.start)))
        return lerp(a, math.log(self.q(lo + 1)), nf - lo)

    # ---------------------------------------------------------------- timeline
    def _build_timeline(self):
        b = self.beat
        self.T = {self.start: -b}
        self.DUR = {self.start: 0.3}
        self.acts = []
        t, n = 0.0, self.start
        first = True
        for spec in self.spec["acts"]:
            a = dict(spec)
            a["t0"] = t
            kind = a["type"]
            if kind == "climb":
                interval = a.get("beats", 1) * b
                ts = t + a.get("lead_beats", 0) * b
                steps = list(range(n + 1, a["to"] + 1))
                pauses = {int(k): v for k, v in a.get("pause_after", {}).items()}
                for i, m in enumerate(steps):
                    self.T[m] = 1 / FPS if (first and i == 0) else ts
                    self.DUR[m] = min(0.3, 0.96 * interval)
                    ts += interval + pauses.get(m, 0) * b
                last = steps[-1]
                rise = a.get("final_rise_beats")
                if rise:
                    self.DUR[last] = min(0.8, 0.8 * rise * b)
                    t = self.T[last] + rise * b
                else:
                    t = self.T[last] + a.get("tail_beats", a.get("beats", 1)) * b
                a["steps"], a["interval"] = steps, interval
                n = last
                first = False
            elif kind in ("payoff", "card"):
                t += a.get("beats", 2) * b
            elif kind == "rewind":
                a["n_from"] = n
                t += a.get("beats", 4) * b
                a["t_end_rewind"] = t
                t += a.get("hold_beats", 0.5) * b
            a["t1"] = t
            self.acts.append(a)
        self.n_max = max(self.T)
        self.duration = round(t * FPS) / FPS
        self.acts[-1]["t1"] = self.duration
        self.rewind = next(a for a in self.acts if a["type"] == "rewind")
        self.hook = self.spec["hook"]

    def act_at(self, t):
        for a in self.acts:
            if a["t0"] <= t < a["t1"]:
                return a
        return self.acts[-1]

    def rewind_n(self, t):
        a = self.rewind
        u = (t - a["t0"]) / (a["t_end_rewind"] - a["t0"])
        return self.start + (a["n_from"] - self.start) * (1 - ease(u))

    def state(self, t):
        """(counter value, displayed quantity)"""
        if t >= self.rewind["t0"]:
            nf = self.rewind_n(t)
            return int(math.ceil(nf - 1e-9)), math.exp(self.log_q(nf))
        n = max(k for k, tk in self.T.items() if tk <= t)
        if n == self.start:
            return n, self.q(n)
        u = ease_out((t - self.T[n]) / self.DUR[n])
        return n, math.exp(lerp(math.log(self.q(n - 1)), math.log(self.q(n)), u))

    # ---------------------------------------------------------------- marks
    def _build_marks(self):
        self.icons, self.markers = [], []
        slots = [150, 330, 470, 620]
        for i, m in enumerate(self.spec.get("marks", [])):
            if "icon" in m:
                lm = LANDMARKS[m["icon"]]
                self.icons.append(dict(kind=m["icon"], h=lm["h"], label=lm["label"], sub=lm["sub"],
                                       x=m.get("x", slots[len(self.icons) % 4]), silent=m.get("silent", False)))
            else:
                self.markers.append(dict(q=float(m["q"]), label=m["label"], sub=m.get("sub") or self.fmt(float(m["q"])),
                                         glyph=m.get("glyph", "line")))
        grid = np.arange(0, self.rewind["t0"], 1 / 600)
        qs = np.array([self.state(t)[1] for t in grid])
        for m in self.icons + self.markers:
            h = m.get("h", m.get("q"))
            idx = np.nonzero(qs >= h)[0] if qs[-1] >= qs[0] else np.nonzero(qs <= h)[0]
            m["cross"] = float(grid[idx[0]]) if len(idx) else None

    # ---------------------------------------------------------------- camera
    def _frame_min(self, n):
        for fr in self.spec.get("camera", {}).get("frame", []):
            if fr["from"] <= n <= fr["to"]:
                return fr["min"]
        return 0.0

    def _push(self, t):
        total = 0.0
        groups, cur = [], None
        for a in self.acts:
            if a["type"] in ("payoff", "card"):
                cur = [a["t0"], a["t1"]] if cur is None else [cur[0], a["t1"]]
            elif cur is not None:
                groups.append(cur)
                cur = None
        for t0, t1 in groups:
            amount = min(0.35, 0.11 * (t1 - t0))
            if t >= t0:
                total += amount * (t - t0) / (t1 - t0) if t < t1 else amount * (1 - ease((t - t1) / 0.5))
        return total

    def _target(self, t):
        n, q = self.state(t)
        return math.log(max(q / 0.72, self._frame_min(n), 1e-300)) + self._push(t)

    def _build_camera(self):
        dt = 1 / 240
        self.cam_t = np.arange(0, self.duration + dt, dt)
        logs, cur = [], None
        T_END = self.duration
        for t in self.cam_t:
            target = self._target(t)
            cur = target if cur is None else cur + (target - cur) * (1 - math.exp(-dt / 0.16))
            if t > T_END - 0.3:
                cur = lerp(cur, target, ease((t - (T_END - 0.3)) / 0.25))
            logs.append(cur)
        self.cam_log = np.array(logs)

    def world_h(self, t, q):
        lg = float(np.interp(t, self.cam_t, self.cam_log))
        fm = self._frame_min(self.state(t)[0])
        return min(max(math.exp(lg), q / 0.86), max(q / 0.55, fm))

    # ---------------------------------------------------------------- text
    def _headline(self, a):
        if a["type"] == "rewind":
            return self.hook
        return a.get("headline") or (self.hook if a is self.acts[0] else None)

    def _fit(self, s, target):
        f = font("ExtraBold", target)
        w = f.getlength(s)
        return target if w <= SAFE_W else max(30, int(target * SAFE_W / w))

    def _draw_head(self, f, lines, a=1.0):
        l1, l2 = lines
        p = min(self._fit(l1, 58), self._fit(l2, 58))
        f.text(l1, 540, 118, p, C["white"], a=a)
        f.text(l2, 540, 118 + p * 1.2, p, C["lav"], a=a)

    def counter_text(self, n):
        q = self.q(n)
        fields = dict(n=f"{n:,}", S="" if n == 1 else "S", s="" if n == 1 else "s", q=self.fmt(q),
                      q_exact=units.count_exact(q))
        for name, fd in self.spec.get("fields", {}).items():
            fields[name] = units.FORMAT[fd["unit"]](_eval(fd["formula"], n, self._q_params))
        l1, l2 = self.spec["counter"]
        return l1.format(**fields), l2.format(**fields)

    # ---------------------------------------------------------------- sound
    def audio(self, mix):
        rng = np.random.default_rng(5)
        twinkle = ladder("D6", 8)
        lad = ladder(self.spec.get("ladder", "D4"), 40)
        lad_hi = ladder("D5", 10)
        prev = None
        for a in self.acts:
            kind = a["type"]
            if kind == "climb":
                fast = a["interval"] < 0.4
                if a.get("lead_beats"):
                    mix.add(a["t0"], mix.sweep(0.5, 400, 6000) * np.linspace(0, 1, 24000) ** 2, 0.07)
                for i, m in enumerate(a["steps"]):
                    if fast:
                        g = 0.10 + 0.08 * i / max(1, len(a["steps"]) - 1)
                        mix.add(self.T[m], mix.pluck(hz(lad_hi[i % 10]), 0.3), g, (i % 5 - 2) * 0.15)
                    else:
                        mix.add(self.T[m], mix.bell(hz(lad[min(m - self.start, 39)])), 0.30)
                        mix.add(self.T[m], mix.sweep(0.2, 3000, 700, 1.0) * np.exp(-mix.t(0.2) * 16), 0.10)
            elif kind == "payoff":
                big = a.get("size") == "big"
                lead = 1.0 if prev and prev["type"] == "climb" and not prev["interval"] < 0.4 else 0.35
                n_lead = int(lead * 48000)
                mix.add(a["t0"] - lead, mix.sweep(lead, 300, 7000 if lead > 0.5 else 8000) * np.linspace(0, 1, n_lead) ** 2, 0.08)
                if big:
                    mix.payoff(a["t0"], chord="D2 A2 D3 F#3 A3 E4 A4", top="A6", gain=1.25)
                    mix.add(a["t0"], mix.pad("D3 A3 D4 F#4 A4", 3.0, attack=0.3, decay=0.6), 0.25)
                else:
                    mix.payoff(a["t0"])
                for i in range(7 if big else 5):
                    mix.add(a["t0"] + 0.3 + i * (0.1 if big else 0.14), mix.grain(hz(twinkle[rng.integers(8)]), 0.12),
                            0.11 if big else 0.08, rng.uniform(-.7, .7))
            elif kind == "card":
                mix.add(a["t0"], mix.bell(hz("A5"), 1.2), 0.14, -0.2)
                cmp_ = a.get("compare")
                if cmp_:
                    mix.add(a["t0"], mix.sweep(1.0, 400, 3500, 1.2) * np.linspace(0, 1, 48000), 0.05, 0.4)
                    for i in range(8):
                        mix.add(a["t0"] + 0.1 + i * 0.11, mix.pluck(hz(ladder("A4", 8)[i]), 0.25, decay=14), 0.08, 0.4)
                    qmain = self.state(a["t0"])[1]
                    if cmp_["q"] > qmain:
                        mix.add(a["t0"] + self._rise(a) * self._ease_inv(qmain / cmp_["q"]), mix.bell(hz("D6"), 1.4), 0.16, 0.3)
                else:
                    for i in range(6):
                        mix.add(a["t0"] + 0.2 + i * 0.2, mix.grain(hz(twinkle[rng.integers(8)])), 0.07, rng.uniform(-.6, .6))
            elif kind == "rewind":
                grid = np.arange(a["t0"], a["t_end_rewind"], 1 / 1000)
                nf = np.array([self.rewind_n(t) for t in grid])
                lad_rw = ladder("D3", 30)
                span = a["n_from"] - self.start
                for m in range(a["n_from"] - 1, self.start - 1, -1):
                    idx = np.nonzero(nf <= m)[0]
                    if len(idx):
                        j = int((m - self.start) / max(1, span) * 21)
                        mix.add(grid[idx[0]], mix.pluck(hz(lad_rw[j]), 0.25, decay=14), 0.12)
                d = a["t_end_rewind"] - a["t0"]
                mix.add(a["t0"], mix.sweep(d, 8000, 300, 0.6) * np.linspace(1, 0, int(d * 48000)), 0.05)
                mix.add(a["t_end_rewind"], mix.bell(hz("D3"), 0.5) * np.exp(-mix.t(0.5) * 4), 0.2)
            prev = a
        for m in self.icons:
            if m["cross"] is not None and not m["silent"]:
                mix.add(m["cross"], mix.pluck(hz("F#6"), 0.5), 0.10, 0.3)
        for m in self.markers:
            if m["cross"] is not None:
                mix.add(m["cross"], mix.bell(hz("A5"), 0.9), 0.16)

    @staticmethod
    def _ease_inv(y):
        lo, hi = 0.0, 1.0
        for _ in range(40):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if ease(mid) < y else (lo, mid)
        return lo

    @staticmethod
    def _rise(a):
        return min(0.9, 0.6 * (a["t1"] - a["t0"]))

    # ---------------------------------------------------------------- picture
    def draw_cover(self, f, t, headline="hook"):
        self.draw(f, t, force_headline=self.hook if headline == "hook" else None)

    def draw(self, f, t, force_headline=None):
        n, q = self.state(t)
        cam = LogCamera(ground_y=GROUND_Y, screen_h=VIEW_H)
        cam.set_height(self.world_h(t, q))
        k = cam.k
        act = self.act_at(t)
        f.line([(60, GROUND_Y), (1020, GROUND_Y)], C["dim"], 3, 0.8)
        self._particles(f, t)
        self._ruler(f, cam, self._ruler_alpha(t))

        if self.unit == "length":
            for m in self.icons:
                r = m["h"] / cam.world_h
                a = ease((r - 0.012) / 0.03) * (1 - ease((r - 0.62) / 0.12))
                if a <= 0.01:
                    continue
                P = icon(f, m["kind"], cam, (m["x"] - cam.x0) / k, C["mint"], a, 4)
                _, ty = P(0, 1.0)
                f.label(m["label"], m["sub"], m["x"], ty - 62, a=a, px=30)

        for m in self.markers:
            r = m["q"] / cam.world_h
            a = ease((r - 0.05) / 0.08) * (1 - ease((r - 0.66) / 0.06))
            if a <= 0.01:
                continue
            y = GROUND_Y - m["q"] * k
            for x in range(90, BAR_X - 40, 36):
                f.line([(x, y), (x + 18, y)], C["lav"], 3, a * 0.7)
            f.label(m["label"], m["sub"], 90, y - 62, a=a, px=30, sub_color=C["lav"])
            self._glyph(f, m["glyph"], 640, y, a, t)

        bar_px = q * k
        pulse = max([1 - (t - tm) / 0.25 for tm in self.T.values() if 0 <= t - tm < 0.25], default=0.0)
        f.line([(BAR_X, GROUND_Y), (BAR_X, GROUND_Y - max(bar_px, 1.5))], C["warm"], 18 + 10 * pulse)
        f.dot(BAR_X, GROUND_Y - bar_px, 6 + 6 * pulse, C["core"], 0.9)

        for a in self.acts:                      # comparison bars on fact cards
            cmp_ = a.get("compare") if a["type"] == "card" else None
            if not cmp_ or t < a["t0"]:
                continue
            alpha = 1 - ease((t - a["t1"]) / 0.3)
            h = cmp_["q"] * ease((t - a["t0"]) / self._rise(a)) * k
            if alpha > 0 and h > 0:
                x = BAR_X + 120
                f.line([(x, GROUND_Y), (x, GROUND_Y - h)], C["pink"], 14, alpha)
                f.label(cmp_["label"], cmp_.get("sub", ""), x, GROUND_Y - h - 66, a=alpha, px=28, anchor="mm", sub_color=C["pink"])

        for a in self.acts:                      # payoff flash + ring
            if a["type"] == "payoff" and 0 <= t - a["t0"] < 1.5:
                s = 1.4 if a.get("size") == "big" else 1.0
                f.flash = max(f.flash, s * math.exp(-(t - a["t0"]) * 3.5))
                v = (t - a["t0"]) / 1.0
                if v < 1:
                    f.circle(BAR_X, GROUND_Y - bar_px, 40 + 520 * v, C["lav"], 3, 0.8 * (1 - v))

        # headline, crossfading over 0.2 s at act changes
        if force_headline:
            self._draw_head(f, force_headline)
        else:
            cur = self._headline(act) or self._last_headline(act)
            u = (t - act["t0"]) / 0.2
            i = self.acts.index(act)
            prev = (self._headline(self.acts[i - 1]) or self._last_headline(self.acts[i - 1])) if i else cur
            if u < 1 and prev != cur:
                self._draw_head(f, prev, 1 - u)
                self._draw_head(f, cur, u)
            else:
                self._draw_head(f, cur)

        l1, l2 = self.counter_text(n)
        f.text(l1, 540, 300, 66, C["white"], "Bold")
        f.text(l2, 540, 384, min(44, self._fit(l2, 44)), C["mint"], "Bold")
        if act["type"] == "climb":
            for step, text in act.get("callouts", {}).items():
                s = int(step)
                nxt = min([tm for m, tm in self.T.items() if m > s], default=act["t1"])
                if self.T.get(s, 1e9) <= t < nxt:
                    f.text(text, 540, 452, min(36, self._fit(text, 36)), C["lav"], "ExtraBold", a=min(1, (t - self.T[s]) * 8))

    def _last_headline(self, act):
        i = self.acts.index(act)
        for a in reversed(self.acts[:i]):
            h = self._headline(a)
            if h:
                return h
        return self.hook

    def _ruler_alpha(self, t):
        a = 1.0
        for i, act in enumerate(self.acts):
            on = 0.0 if act.get("ruler") is False else 1.0
            before = (0.0 if self.acts[i - 1].get("ruler") is False else 1.0) if i else on
            if t >= act["t0"]:
                a = lerp(before, on, ease((t - act["t0"]) / 0.35))
        return a

    def _ruler(self, f, cam, a):
        if a <= 0:
            return
        lo = self.spec.get("ruler_min", 0)
        e0 = math.floor(math.log10(cam.world_h)) - 2
        for e in range(e0, e0 + 4):
            for m in (1, 2, 5):
                v = m * 10.0 ** e
                if v < lo:
                    continue
                y = GROUND_Y - v * cam.k
                if 520 < y < GROUND_Y - 4:
                    big = m == 1
                    f.line([(44, y), (66 if big else 58, y)], C["dim"], 3 if big else 2, a * (0.9 if big else 0.5))
                    if big:
                        f.text(self.fmt(v), 74, y, 22, C["dim"], "SemiBold", anchor="lm", a=a * 0.9)
        f.line([(44, 520), (44, GROUND_Y)], C["dim"], 2, a * 0.35)

    def _particles(self, f, t):
        rng = np.random.default_rng(11)
        T_END = self.duration
        for i in range(34):
            x0, y0 = rng.uniform(40, 1040), rng.uniform(0, 1920)
            cyc, ph, r = rng.integers(1, 4), rng.uniform(0, 6.28), rng.uniform(1.6, 3.2)
            y = (y0 - 1920 * t / T_END) % 1920
            x = x0 + 12 * math.sin(2 * math.pi * t / T_END + ph)
            a = 0.18 + 0.17 * math.sin(2 * math.pi * cyc * t / T_END + ph)
            f.dot(x, y, r, C["lav"] if i % 3 else C["core"], a)

    def _glyph(self, f, g, x, y, a, t):
        if g == "moon":
            f.circle(x, y, 18, C["white"], 3, a)
        elif g == "sun":
            f.circle(x, y, 30, C["warm"], 4, a, fill=0.25)
        elif g == "planet":
            f.circle(x, y, 16, C["sky"], 3, a)
        elif g == "star":
            f.dot(x, y, 7, C["white"], a)
        elif g == "mount":
            f.line([(x - 40, y + 30), (x, y), (x + 40, y + 30)], C["mint"], 3, a)
        elif g == "person":
            f.circle(x, y - 26, 8, C["mint"], 3, a)
            f.line([(x, y - 18), (x, y + 4)], C["mint"], 3, a)
        elif g == "galaxy":
            rng = np.random.default_rng(3)
            cx, cy, R = 390, y + 150, 230
            for arm in range(2):
                for i in range(70):
                    th = i / 70 * 3.2 * math.pi + arm * math.pi + t * 0.25
                    rr = R * (0.08 + 0.92 * i / 70)
                    px = cx + rr * math.cos(th) + rng.normal(0, 6)
                    py = cy + 0.42 * rr * math.sin(th) + rng.normal(0, 4)
                    f.dot(px, py, 2.2 + 2.5 * (1 - i / 70), C["core"] if i < 12 else C["lav"], a * (0.9 - 0.5 * i / 70))
            f.dot(cx, cy, 14, C["core"], a)

    def _key_times(self):
        ts = [0.0]
        for a in self.acts:
            if a["type"] == "climb":
                st = a["steps"]
                for m in st[:: max(1, len(st) // 3)]:
                    ts.append(self.T[m] + 0.2)
            else:
                ts.append(a["t0"] + 0.4)
        ts.append(self.duration - 1 / FPS)
        return sorted(set(round(t, 2) for t in ts if 0 <= t < self.duration))
