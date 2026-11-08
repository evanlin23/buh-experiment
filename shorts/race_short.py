"""RaceShort: balls race down ramps of different shapes, with exact frictionless physics.

A different format from the ladder: no bar and no log camera. Curves are drawn in full,
balls race on them with trails, a live timer runs, a leaderboard fills in, and the sound is
a click every fixed distance a ball travels (so a faster ball literally clicks faster), plus a
bell as each one finishes.

Acts: race -> payoff -> card (ghost replay) -> tauto (balls dropped from different heights on
the cycloid all arrive together) -> payoff -> rewind (time runs backwards to frame 0).
"""
import math

import numpy as np

from engine import C, FPS, ease, font, hz, ladder, lerp

SAFE_W = 960
PALETTE = {"lav": C["lav"], "sky": C["sky"], "warm": C["warm"], "pink": C["pink"], "mint": C["mint"], "white": C["white"]}
NOTES = ["D6", "A5", "F#5", "D5", "A4"]          # finish bells, 1st to 5th


class Curve:
    """A ramp from A to B sampled densely, with its frictionless time table."""

    def __init__(self, kind, A, B, r, g, depth=0.55, n=900):
        (ax, ay), (bx, by) = A, B
        X, Y = bx - ax, by - ay
        u = np.linspace(0, 1, n)
        if kind == "straight":
            x, y = ax + X * u, ay + Y * u
        elif kind == "cycloid":
            th = math.pi * u
            x, y = ax + r * (th - np.sin(th)), ay + r * (1 - np.cos(th))
        elif kind == "circle":
            R = (X * X + Y * Y) / (2 * X)
            cx, cy = ax + R, ay
            phB = math.atan2(by - cy, bx - cx) % (2 * math.pi)
            ph = math.pi + (phB - math.pi) * u
            x, y = cx + R * np.cos(ph), cy + R * np.sin(ph)
        elif kind == "dip":
            x, y = ax + X * u, ay + Y * u + depth * Y * np.sin(math.pi * u)
        else:
            raise ValueError(kind)
        self.x, self.y = x, y
        ds = np.hypot(np.diff(x), np.diff(y))
        self.s = np.concatenate([[0], np.cumsum(ds)])
        v = np.sqrt(np.maximum(0, 2 * g * (y - ay)))
        vm = (v[1:] + v[:-1]) / 2                   # exact for constant acceleration from rest
        self.t = np.concatenate([[0], np.cumsum(ds / np.maximum(vm, 1e-9))])
        self.T = float(self.t[-1])

    def at(self, t):
        t = min(max(t, 0.0), self.T)
        return float(np.interp(t, self.t, self.x)), float(np.interp(t, self.t, self.y))

    def dist(self, t):
        return float(np.interp(min(max(t, 0), self.T), self.t, self.s))

    def points(self, step=6):
        return list(zip(self.x[::step], self.y[::step])) + [(self.x[-1], self.y[-1])]


class RaceShort:
    def __init__(self, v, spec):
        self.v, self.spec = v, spec
        self.beat = 60.0 / spec.get("bpm", 120)
        rc = spec["race"]
        self.r = rc.get("r", 230)
        self.A = tuple(rc.get("A", (180, 600)))
        self.B = (self.A[0] + math.pi * self.r, self.A[1] + 2 * self.r)
        self.g = self.r * (math.pi / rc.get("seconds", 2.8)) ** 2       # cycloid time = `seconds`
        self.curves = []
        for c in rc["curves"]:
            cv = Curve(c["kind"], self.A, self.B, self.r, self.g, c.get("depth", 0.55))
            cv.name, cv.color = c["name"], PALETTE[c.get("color", "white")]
            self.curves.append(cv)
        self.order = sorted(range(len(self.curves)), key=lambda i: self.curves[i].T)
        self.cyc = next(c for c in self.curves if c is not None and "CYCLOID" in c.name.upper())
        self.click = rc.get("click_px", 55)
        self._timeline()
        self.key_times = self._key_times()

    # ---------------------------------------------------------------- timeline
    def _timeline(self):
        b, t = self.beat, 0.0
        self.acts = []
        race_len = max(c.T for c in self.curves)
        for spec in self.spec["acts"]:
            a = dict(spec)
            a["t0"] = t
            k = a["type"]
            if k == "race":
                a["start"] = 1 / FPS
                t = a["start"] + race_len + a.get("tail_beats", 0.5) * b
            elif k in ("payoff", "card"):
                t += a.get("beats", 2) * b
            elif k == "tauto":
                a["start"] = t + a.get("lead_beats", 0.5) * b
                a["T"] = self.cyc.T
                t = a["start"] + self.cyc.T + a.get("tail_beats", 0.25) * b
            elif k == "rewind":
                a["end"] = t + a.get("beats", 4) * b
                t = a["end"] + a.get("hold_beats", 0.5) * b
            a["t1"] = t
            self.acts.append(a)
        self.duration = round(t * FPS) / FPS
        self.acts[-1]["t1"] = self.duration
        self.race = next(a for a in self.acts if a["type"] == "race")
        self.tauto = next((a for a in self.acts if a["type"] == "tauto"), None)
        self.rewind = next(a for a in self.acts if a["type"] == "rewind")
        self.race_len = race_len

    def act_at(self, t):
        for a in self.acts:
            if a["t0"] <= t < a["t1"]:
                return a
        return self.acts[-1]

    def race_clock(self, t):
        """Race time shown on the timer and used for ball positions."""
        if t >= self.rewind["t0"]:
            u = ease((t - self.rewind["t0"]) / (self.rewind["end"] - self.rewind["t0"]))
            return self.race_len * (1 - u)
        return min(self.race_len, max(0.0, t - self.race["start"]))   # freezes at the last finish

    # ---------------------------------------------------------------- tautochrone
    def tauto_balls(self, t):
        """(x, y, s_from_bottom) for balls released from rest at different heights on the cycloid."""
        a = self.tauto
        if a is None or t < a["t0"] or t >= self.rewind["t0"] + 0.4:
            return []
        n = a.get("balls", 5)
        w = math.sqrt(self.g / (4 * self.r))
        tt = min(max(0.0, t - a["start"]), a["T"])
        out = []
        for i in range(n):
            th0 = 0.35 + (math.pi - 0.9) * i / max(1, n - 1)      # release points along the arch
            s0 = 4 * self.r * math.cos(th0 / 2)
            s = s0 * math.cos(w * tt)
            th = 2 * math.acos(max(-1, min(1, s / (4 * self.r))))
            out.append((self.A[0] + self.r * (th - math.sin(th)), self.A[1] + self.r * (1 - math.cos(th)), s0 - s, i))
        return out

    # ---------------------------------------------------------------- text
    def _fit(self, s, target, weight="ExtraBold"):
        w = font(weight, target).getlength(s)
        return target if w <= SAFE_W else max(28, int(target * SAFE_W / w))

    def _head_for(self, a):
        if a["type"] in ("race", "rewind"):
            return self.spec["hook"]
        if a.get("headline"):
            return a["headline"]
        i = self.acts.index(a)
        return self._head_for(self.acts[i - 1]) if i else self.spec["hook"]

    def _draw_head(self, f, lines, a=1.0):
        l1, l2 = lines
        p = min(self._fit(l1, 60), self._fit(l2, 60))
        f.text(l1, 540, 118, p, C["white"], a=a)
        f.text(l2, 540, 118 + p * 1.2, p, C["lav"], a=a)

    # ---------------------------------------------------------------- sound
    def audio(self, mix):
        rng = np.random.default_rng(9)
        st = self.race["start"]
        lad = ladder("D4", 12)
        mix.add(st, mix.bell(hz("A5"), 0.6), 0.22)              # the start beep
        mix.add(st, mix.tick(3200), 0.15)
        for rank, i in enumerate(self.order):     # distance clicks, pitched per curve; finish bells
            c = self.curves[i]
            pitch = hz(lad[2 + 2 * i])
            k = 1
            while k * self.click < c.s[-1]:
                tk = float(np.interp(k * self.click, c.s, c.t))
                mix.add(st + tk, mix.pluck(pitch, 0.12, decay=30), 0.10, -0.6 + 1.2 * i / max(1, len(self.curves) - 1))
                k += 1
            mix.add(st + c.T, mix.bell(hz(NOTES[rank]), 1.2), 0.30 if rank == 0 else 0.18)
        for a in self.acts:
            if a["type"] == "payoff":
                big = a.get("size") == "big"
                mix.add(a["t0"] - 0.35, mix.sweep(0.35, 500, 8000) * np.linspace(0, 1, int(0.35 * 48000)) ** 2, 0.07)
                if big:
                    mix.payoff(a["t0"], chord="D2 A2 D3 F#3 A3 E4 A4", top="A6", gain=1.2)
                else:
                    mix.payoff(a["t0"], gain=0.9)
                for j in range(5):
                    mix.add(a["t0"] + 0.3 + j * 0.13, mix.grain(hz(ladder("D6", 8)[rng.integers(8)]), 0.12), 0.09, rng.uniform(-.7, .7))
            elif a["type"] == "card":
                chord = ladder("D5", 6)
                for j in range(int(round((a["t1"] - a["t0"]) / self.beat))):
                    mix.add(a["t0"] + j * self.beat, mix.pluck(hz(chord[j % 6]), 0.35), 0.12, (j % 3 - 1) * 0.3)
                if a.get("replay"):               # ghost replay clicks, quieter, at double speed
                    c = self.cyc
                    for k in range(1, int(c.s[-1] / self.click)):
                        mix.add(a["t0"] + float(np.interp(k * self.click, c.s, c.t)) / 2, mix.tick(2600), 0.05)
            elif a["type"] == "tauto":
                mix.add(a["t0"], mix.sweep(a["start"] - a["t0"], 400, 6000) * np.linspace(0, 1, int((a["start"] - a["t0"]) * 48000)) ** 2, 0.06)
                for j, nm in enumerate(ladder("D4", a.get("balls", 5))):
                    mix.add(a["start"], mix.pluck(hz(nm), 0.4), 0.10, -0.6 + 0.3 * j)
                # every ball clicks per distance travelled; they all land on the same instant
                w = math.sqrt(self.g / (4 * self.r))
                for (_, _, _, j) in self.tauto_balls(a["start"]):
                    th0 = 0.35 + (math.pi - 0.9) * j / max(1, a.get("balls", 5) - 1)
                    s0 = 4 * self.r * math.cos(th0 / 2)
                    k = 1
                    while k * self.click < s0:
                        tk = math.acos(1 - k * self.click / s0) / w
                        mix.add(a["start"] + tk, mix.pluck(hz(ladder("F#5", 5)[j]), 0.1, decay=34), 0.07, -0.6 + 0.3 * j)
                        k += 1
                arrive = a["start"] + a["T"]
                for j, nm in enumerate(["D4", "A4", "D5", "F#5", "A5"]):
                    mix.add(arrive, mix.bell(hz(nm), 1.6), 0.16)
        rw = self.rewind
        d = rw["end"] - rw["t0"]
        mix.add(rw["t0"], mix.sweep(d, 8000, 300, 0.6) * np.linspace(1, 0, int(d * 48000)), 0.05)
        grid = np.arange(rw["t0"], rw["end"], 1 / 600)
        clock = np.array([self.race_clock(t) for t in grid])
        for i, c in enumerate(self.curves):       # clicks again, backwards
            dist = np.array([c.dist(x) for x in clock])
            marks = np.floor(dist / self.click)
            for j in np.nonzero(np.diff(marks) < 0)[0]:
                mix.add(grid[j], mix.tick(1800 + 300 * i), 0.05)
        mix.add(rw["end"], mix.bell(hz("D3"), 0.5) * np.exp(-mix.t(0.5) * 4), 0.2)

    # ---------------------------------------------------------------- picture
    def draw_cover(self, f, t, headline="hook"):
        self.draw(f, t, force_head=self.spec["hook"])

    def _zoom(self, t):
        """Slow push-in through the holds (continuous, back to 1 before the loop point)."""
        z = 0.0
        for a in self.acts:
            if a["type"] in ("payoff", "card") and t >= a["t0"]:
                z += 0.05 * min(1.0, (t - a["t0"]) / (a["t1"] - a["t0"]))
        if t >= self.rewind["t0"]:
            z *= 1 - ease((t - self.rewind["t0"]) / 0.6)
        return 1 + z

    def draw(self, f, t, force_head=None):
        act = self.act_at(t)
        z = self._zoom(t)
        cx, cy = 540, (self.A[1] + self.B[1]) / 2
        P = lambda p: (cx + (p[0] - cx) * z, cy + (p[1] - cy) * z)  # noqa: E731
        self._particles(f, t)
        rt = self.race_clock(t)
        # ramps
        for i, c in enumerate(self.curves):
            f.line([P(p) for p in c.points()], c.color, 5, 0.85)
        f.dot(*P(self.A), 9, C["white"], 0.9)
        bx, by = P(self.B)
        f.line([(bx + 8, by - 40), (bx + 8, by + 22)], C["white"], 4, 0.8)      # finish post
        # ghost replay during cards
        for a in self.acts:
            if a["type"] == "card" and a.get("replay") and a["t0"] <= t < a["t1"]:
                gt = (t - a["t0"]) * 2
                for c in self.curves:
                    f.dot(*P(c.at(gt)), 12, c.color, 0.35)
        # balls with trails
        show_race = not (self.tauto and self.tauto["t0"] <= t < self.rewind["t0"])
        for i, c in enumerate(self.curves):
            if not show_race:
                break
            for k in range(1, 7):
                tk = rt - 0.035 * k
                if tk > 0:
                    f.dot(*P(c.at(tk)), 16 - 1.8 * k, c.color, 0.5 - 0.07 * k)
            x, y = P(c.at(rt))
            f.dot(x, y, 18, c.color, 1.0)
            f.dot(x, y, 7, C["core"], 1.0)
        # tautochrone balls
        for (x, y, _, j) in self.tauto_balls(t):
            a = 1.0 if t < self.rewind["t0"] else 1 - (t - self.rewind["t0"]) / 0.4
            col = PALETTE[["warm", "pink", "sky", "mint", "lav"][j % 5]]
            f.dot(*P((x, y)), 18, col, a)
            f.dot(*P((x, y)), 7, C["core"], a)
        # the start signal: a ring bursts from the start point on frame 1
        v0 = (t - self.race["start"]) / 0.5
        if 0 <= v0 < 1:
            f.circle(*P(self.A), 16 + 150 * v0, C["white"], 4, 0.9 * (1 - v0))
            f.flash = max(f.flash, 0.35 * (1 - v0))
        # finish flashes and payoff rings
        for rank, i in enumerate(self.order):
            tf = self.race["start"] + self.curves[i].T
            if 0 <= t - tf < 0.6 and t < self.rewind["t0"]:
                v = (t - tf) / 0.6
                f.circle(bx, by, 20 + 90 * v, self.curves[i].color, 3, 0.8 * (1 - v))
        for a in self.acts:
            if a["type"] == "payoff" and 0 <= t - a["t0"] < 1.2:
                s = 1.3 if a.get("size") == "big" else 0.9
                f.flash = max(f.flash, s * math.exp(-(t - a["t0"]) * 3.5))
                v = (t - a["t0"]) / 1.0
                if v < 1:
                    f.circle(bx, by, 40 + 520 * v, C["lav"], 3, 0.8 * (1 - v))
            if a["type"] == "card" and a["t0"] <= t < a["t1"]:
                v = ((t - a["t0"]) % self.beat) / self.beat
                f.circle(bx, by, 20 + 140 * v, C["mint"], 3, 0.7 * (1 - v))
            if a["type"] == "tauto" and 0 <= t - (a["start"] + a["T"]) < 0.8:
                v = (t - a["start"] - a["T"]) / 0.8
                f.circle(bx, by, 30 + 400 * v, C["warm"], 4, 0.9 * (1 - v))
                f.flash = max(f.flash, 1.1 * (1 - v))

        # headline (crossfade 0.2 s), timer, leaderboard
        cur = force_head or self._head_for(act)
        i = self.acts.index(act)
        prev = self._head_for(self.acts[i - 1]) if i else cur
        u = (t - act["t0"]) / 0.2
        if not force_head and u < 1 and prev != cur:
            self._draw_head(f, prev, 1 - u)
            self._draw_head(f, cur, u)
        else:
            self._draw_head(f, cur)
        if self.tauto and self.tauto["t0"] <= t < self.rewind["t0"]:
            tt = min(max(0.0, t - self.tauto["start"]), self.tauto["T"])
            f.text(f"{tt:.2f} s", 540, 300, 70, C["white"], "Bold")
            f.text(self.spec.get("tauto_label", "ALL ON THE SAME CURVE"), 540, 386, 36, C["mint"], "Bold")
        else:
            f.text(f"{rt:.2f} s", 540, 300, 70, C["white"], "Bold")
        y0 = by + 90
        for rank, i in enumerate(self.order):
            c = self.curves[i]
            if rt >= c.T and (t < self.rewind["t0"] or rt >= c.T):
                if self.tauto and self.tauto["t0"] <= t < self.rewind["t0"]:
                    continue
                y = y0 + rank * 58
                f.dot(170, y, 12, c.color, 1.0)
                f.text(f"{rank + 1}", 210, y, 40, C["white"], "Bold", anchor="lm")
                f.text(c.name, 260, y, 40, C["white"], "Bold", anchor="lm")
                f.text(f"{c.T * self.spec['race'].get('time_scale', 1):.2f} s", 910, y, 40, c.color, "Bold", anchor="rm")

    def _particles(self, f, t):
        """Faint drifting motes, periodic over the loop so the seam stays exact."""
        rng = np.random.default_rng(23)
        T_END = self.duration
        for i in range(30):
            x0, y0 = rng.uniform(40, 1040), rng.uniform(0, 1920)
            cyc, ph, r = rng.integers(1, 4), rng.uniform(0, 6.28), rng.uniform(1.6, 3.0)
            y = (y0 + 1920 * t / T_END) % 1920          # drifts down here (the ladder's drift up)
            x = x0 + 10 * math.sin(2 * math.pi * t / T_END + ph)
            f.dot(x, y, r, C["sky"] if i % 3 else C["core"], 0.16 + 0.14 * math.sin(2 * math.pi * cyc * t / T_END + ph))

    def _key_times(self):
        ts = [0.0, 0.6, 1.4, 2.2]
        for a in self.acts[1:]:
            ts.append(a["t0"] + 0.4)
            if a["type"] == "tauto":
                ts += [a["start"] + a["T"] * 0.5, a["start"] + a["T"] + 0.1]
        ts.append(self.duration - 1 / FPS)
        return sorted(set(round(x, 2) for x in ts if 0 <= x < self.duration))
