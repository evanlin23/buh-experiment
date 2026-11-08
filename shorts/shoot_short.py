"""ShootShort: projectile rounds under exact gravity (the monkey-and-hunter demo, and kin).

Fifth format. A side-on scene in metres: a launcher, a target that drops the instant each shot
is fired, darts on true parabolas with trails. Each round has its own timer; a results board
fills in (hit height or MISS). Sound: a pop on firing, a click per 2 m a dart flies, a bell for a
hit pitched by its height, a thud when the target lands first. A 'why' card draws the proof:
dart and target fall the same ½gt² below where they would have been.

Acts: shot (v) ... payoff ... card (why/plain) ... rewind.
"""
import math

import numpy as np

from engine import C, FPS, ease, font, hz, ladder, lerp

SAFE_W = 960
G = 9.81


class ShootShort:
    def __init__(self, v, spec):
        self.v, self.spec = v, spec
        self.beat = 60.0 / spec.get("bpm", 120)
        sc = spec["scene"]
        self.target = tuple(sc.get("target", (20.0, 10.0)))     # metres
        self.theta = math.atan2(self.target[1], self.target[0])  # aim straight at the target
        self.ppm = sc.get("ppm", 43.0)                           # pixels per metre
        self.origin = (sc.get("x0", 120), sc.get("ground", 1290))
        self.t_land = math.sqrt(2 * self.target[1] / G)
        self.click_m = sc.get("click_m", 2.0)
        self._timeline()
        self.key_times = self._key_times()

    # ---------------------------------------------------------------- physics
    def shot(self, vel, t):
        """(dart x, y), (target x, y), state ('fly' | 'hit' | 'miss'), t_end for a shot at speed vel."""
        tx, ty = self.target
        t_hit = tx / (vel * math.cos(self.theta))
        hit = t_hit < self.t_land
        t_end = t_hit if hit else self.t_land
        tt = min(max(t, 0.0), t_end)
        dart = (vel * math.cos(self.theta) * tt, vel * math.sin(self.theta) * tt - 0.5 * G * tt * tt)
        tm = min(max(t, 0.0), self.t_land)       # the monkey keeps falling until it lands...
        tgt = (tx, ty - 0.5 * G * tm * tm)
        if hit and t > t_hit:                    # ...carrying the dart with it after a hit
            dart = tgt
        state = "fly" if t < t_end else ("hit" if hit else "miss")
        return dart, tgt, state, t_end, hit

    def S(self, p):
        return (self.origin[0] + p[0] * self.ppm, self.origin[1] - p[1] * self.ppm)

    # ---------------------------------------------------------------- timeline
    def _timeline(self):
        b, t = self.beat, 0.0
        self.acts = []
        for spec in self.spec["acts"]:
            a = dict(spec)
            a["t0"] = t
            if a["type"] == "shot":
                a["fire"] = t + (1 / FPS if t == 0 else 0.0)
                _, _, _, a["t_end"], a["hit"] = self.shot(a["v"], 0)
                t = a["fire"] + self.t_land + a.get("tail_beats", 1) * b     # every round runs until touchdown
            elif a["type"] in ("payoff", "card"):
                t += a.get("beats", 2) * b
            elif a["type"] == "rewind":
                a["end"] = t + a.get("beats", 4) * b
                t = a["end"] + a.get("hold_beats", 0.5) * b
            a["t1"] = t
            self.acts.append(a)
        self.duration = round(t * FPS) / FPS
        self.acts[-1]["t1"] = self.duration
        self.shots = [a for a in self.acts if a["type"] == "shot"]
        self.rewind = next(a for a in self.acts if a["type"] == "rewind")

    def act_at(self, t):
        for a in self.acts:
            if a["t0"] <= t < a["t1"]:
                return a
        return self.acts[-1]

    def current_shot(self, t):
        """The shot whose dart is on screen at time t, and the time since it was fired."""
        if t >= self.rewind["t0"]:
            last = self.shots[-1]
            u = ease((t - self.rewind["t0"]) / (self.rewind["end"] - self.rewind["t0"]))
            if u >= 1:
                return self.shots[0], 0.0
            return last, self.t_land * (1 - u)
        prev = None
        for a in self.shots:
            if a["t0"] <= t:
                prev = a
        prev = prev or self.shots[0]
        return prev, max(0.0, t - prev["fire"])

    # ---------------------------------------------------------------- text
    def _fit(self, s, target, weight="ExtraBold"):
        w = font(weight, target).getlength(s)
        return target if w <= SAFE_W else max(28, int(target * SAFE_W / w))

    def _head_for(self, a):
        if a["type"] in ("shot", "rewind"):
            return a.get("headline") or self.spec["hook"]
        return a.get("headline") or self.spec["hook"]

    def _draw_head(self, f, lines, a=1.0):
        l1, l2 = lines
        p = min(self._fit(l1, 60), self._fit(l2, 60))
        f.text(l1, 540, 118, p, C["white"], a=a)
        f.text(l2, 540, 118 + p * 1.2, p, C["lav"], a=a)

    # ---------------------------------------------------------------- sound
    def audio(self, mix):
        rng = np.random.default_rng(13)
        notes = ladder("D4", 16)
        for a in self.shots:
            f0 = a["fire"]
            mix.add(f0, mix.burst(0.25, 18), 0.20)                                        # pop
            mix.add(f0, np.sin(2 * np.pi * 70 * mix.t(0.2)) * np.exp(-mix.t(0.2) * 22), 0.35)
            whistle = np.sin(2 * np.pi * np.cumsum(1400 - 900 * mix.t(0.6) / 0.6) / 48000) * np.exp(-mix.t(0.6) * 3)
            mix.add(f0, whistle, 0.05, 0.6)                                               # target lets go
            vx = a["v"] * math.cos(self.theta)
            k = 1
            while True:                                                                    # click per 2 m flown
                tk = self.click_m * k / a["v"]
                if tk >= a["t_end"]:
                    break
                mix.add(f0 + tk, mix.pluck(hz(notes[4 + (k % 5)]), 0.1, decay=34), 0.08, -0.6 + 1.2 * min(1, vx * tk / self.target[0]))
                k += 1
            end = f0 + a["t_end"]
            if a["hit"]:
                hy = self.target[1] - 0.5 * G * a["t_end"] ** 2
                mix.add(end, mix.bell(hz(notes[int(2 + 12 * hy / self.target[1])]), 1.3), 0.30, 0.6)
                mix.add(end, mix.burst(0.4, 10), 0.06, 0.6)
                mix.add(f0 + self.t_land, np.sin(2 * np.pi * 60 * mix.t(0.3)) * np.exp(-mix.t(0.3) * 14), 0.25, 0.6)
            else:
                mix.add(end, np.sin(2 * np.pi * 55 * mix.t(0.4)) * np.exp(-mix.t(0.4) * 9), 0.5, 0.6)
                mix.add(end, mix.pluck(hz("D3"), 0.5, decay=8), 0.2, 0.6)
        for a in self.acts:
            if a["type"] == "payoff":
                mix.add(a["t0"] - 0.35, mix.sweep(0.35, 500, 8000) * np.linspace(0, 1, int(0.35 * 48000)) ** 2, 0.07)
                mix.payoff(a["t0"], gain=1.1)
                for j in range(5):
                    mix.add(a["t0"] + 0.3 + j * 0.13, mix.grain(hz(ladder("D6", 8)[rng.integers(8)]), 0.12), 0.09, rng.uniform(-.7, .7))
            elif a["type"] == "card":
                chord = ladder("D5", 6)
                for j in range(int(round((a["t1"] - a["t0"]) / self.beat))):
                    mix.add(a["t0"] + j * self.beat, mix.pluck(hz(chord[j % 6]), 0.35), 0.12, (j % 3 - 1) * 0.3)
        rw = self.rewind
        d = rw["end"] - rw["t0"]
        mix.add(rw["t0"], mix.sweep(d, 8000, 300, 0.6) * np.linspace(1, 0, int(d * 48000)), 0.05)
        for j in range(len(self.shots)):
            mix.add(rw["t0"] + d * (j + 1) / (len(self.shots) + 1), mix.tick(1800 + 200 * j), 0.08)
        mix.add(rw["end"], mix.bell(hz("D3"), 0.5) * np.exp(-mix.t(0.5) * 4), 0.2)

    # ---------------------------------------------------------------- picture
    def draw_cover(self, f, t, headline="hook"):
        self.draw(f, t, force_head=self.spec["hook"])

    def _monkey(self, f, x, y, a=1.0, hit=0.0):
        col, k = C["warm"], 1.3
        f.circle(x, y - 26 * k, 17 * k, col, 4, a)             # head
        f.circle(x - 17 * k, y - 38 * k, 7 * k, col, 3, a)     # ears
        f.circle(x + 17 * k, y - 38 * k, 7 * k, col, 3, a)
        f.circle(x, y + 6 * k, 16 * k, col, 4, a)              # body
        f.line([(x - 14 * k, y - 4 * k), (x - 28 * k, y - 30 * k)], col, 4, a)   # arms up (it just let go)
        f.line([(x + 14 * k, y - 4 * k), (x + 28 * k, y - 30 * k)], col, 4, a)
        if hit > 0:
            f.circle(x, y, 26 + 120 * (1 - hit), C["white"], 4, hit)

    def draw(self, f, t, force_head=None):
        act = self.act_at(t)
        shot, ts = self.current_shot(t)
        why_ref = None
        if act.get("why"):                       # explaining: replay the reference shot as a live proof
            why_ref = next(s_ for s_ in self.shots if s_["hit"] and s_["v"] == act.get("why_v", s_["v"]))
            cycle = why_ref["t_end"] + 0.35
            shot, ts = why_ref, min(((t - act["t0"]) % cycle), why_ref["t_end"])
        elif act.get("replay_v") is not None:    # a card that replays a shot (e.g. the miss), never a frozen frame
            shot = next(s_ for s_ in self.shots if s_["v"] == act["replay_v"])
            cycle = self.t_land + 0.3
            ts = min((t - act["t0"]) % cycle, self.t_land)
        dart, tgt, state, t_end, hit = self.shot(shot["v"], ts)
        self._particles(f, t)
        gx, gy = self.S((0, 0))
        tx, ty = self.S(self.target)
        # ground, tree with branch, launcher, aim line
        f.line([(60, gy), (1020, gy)], C["dim"], 3, 0.8)
        f.line([(tx + 55, gy), (tx + 55, ty - 60)], C["mint"], 5, 0.8)
        f.line([(tx - 30, ty - 44), (tx + 55, ty - 54)], C["mint"], 5, 0.8)
        ca, sa = math.cos(self.theta), math.sin(self.theta)
        f.line([(gx, gy), (gx + 70 * ca, gy - 70 * sa)], C["white"], 10, 0.9)
        f.circle(gx, gy, 20, C["white"], 4, 0.9)
        for i in range(0, 40):
            u0, u1 = i / 40, (i + 0.5) / 40
            f.line([(lerp(gx, tx, u0), lerp(gy, ty, u0)), (lerp(gx, tx, u1), lerp(gy, ty, u1))], C["lav"], 2, 0.35)
        # muzzle flash on each fire
        for a in self.shots:
            v0 = (t - a["fire"]) / 0.45
            if 0 <= v0 < 1 and t < self.rewind["t0"]:
                f.circle(gx + 60 * ca, gy - 60 * sa, 14 + 130 * v0, C["white"], 4, 0.9 * (1 - v0))
                f.flash = max(f.flash, 0.3 * (1 - v0))
        # dart with trail, monkey
        if ts > 0 or t >= self.rewind["t0"]:
            for k in range(1, 8):
                tk = ts - 0.03 * k
                if tk > 0:
                    d2, *_ = self.shot(shot["v"], tk)
                    f.dot(*self.S(d2), 11 - 1.2 * k, C["sky"], 0.55 - 0.06 * k)
            f.dot(*self.S(dart), 12, C["sky"], 1.0)
            f.dot(*self.S(dart), 5, C["core"], 1.0)
        mx, my = self.S(tgt)
        hit_glow = 0.0
        if state == "hit" and t < self.rewind["t0"]:
            hit_glow = max(0.0, 1 - (ts - t_end) / 0.6)
        self._monkey(f, mx, my - 10, 1.0, hit_glow)
        if state == "miss" and t < self.rewind["t0"]:
            v = min(1.0, (ts - t_end) / 0.6)
            f.circle(mx, gy, 20 + 90 * v, C["pink"], 4, 0.9 * (1 - v))

        # the proof: both fall the same 1/2 g t^2 below where they would have been
        for a in self.acts:
            if a["type"] in ("payoff", "card") and a.get("why") and a["t0"] <= t < a["t1"]:
                ref = why_ref
                th = ts                                  # the replay clock: arrows grow as both fall
                u = 1.0
                straight = (ref["v"] * ca * th, ref["v"] * sa * th)
                drop = 0.5 * G * th * th
                for pt0, label in ((straight, "dart"), (self.target, "monkey")):
                    x0, y0 = self.S(pt0)
                    x1, y1 = self.S((pt0[0], pt0[1] - drop))
                    off = -36 if label == "dart" else 36
                    f.line([(x0 + off, y0), (x1 + off, y1)], C["pink"], 5, 0.95)
                    f.line([(x1 + off - 10, y1 - 14), (x1 + off, y1), (x1 + off + 10, y1 - 14)], C["pink"], 4, 0.95)
                f.text("½gt²", tx - 96, (ty + self.S((0, self.target[1] - drop))[1]) / 2, 34, C["pink"], "Bold", anchor="rm", a=u)
                pts = [self.S(self.shot(ref["v"], ref["t_end"] * i / 40)[0]) for i in range(41)]
                f.line(pts, C["sky"], 3, 0.5)
            if a["type"] == "payoff" and 0 <= t - a["t0"] < 1.2:
                f.flash = max(f.flash, 1.1 * math.exp(-(t - a["t0"]) * 3.5))
                v = (t - a["t0"]) / 1.0
                if v < 1:
                    f.circle(tx, ty, 40 + 480 * v, C["lav"], 3, 0.8 * (1 - v))
            if a["type"] == "card" and a["t0"] <= t < a["t1"]:
                v = ((t - a["t0"]) % self.beat) / self.beat
                f.circle(mx, my, 24 + 120 * v, C["mint"], 3, 0.7 * (1 - v))

        # text: headline, timer + dart speed, results board
        end_state = t >= self.rewind["end"]
        cur = force_head or (self.spec["hook"] if end_state else self._head_for(act))
        i = self.acts.index(act)
        prev = self._head_for(self.acts[i - 1]) if i else cur
        u = (t - act["t0"]) / 0.2
        if not force_head and not end_state and u < 1 and prev != cur:
            self._draw_head(f, prev, 1 - u)
            self._draw_head(f, cur, u)
        else:
            self._draw_head(f, cur)
        show = self.shots[0] if end_state else shot
        clock = 0.0 if end_state else min(ts, self.t_land)
        f.text(f"{clock:.2f} s", 540, 300, 70, C["white"], "Bold")
        f.text(f"DART AT {show['v']:g} M/S", 540, 386, 38, C["sky"], "Bold")
        y0 = gy + 70
        done = [a for a in self.shots if t >= a["fire"] + a["t_end"]]
        if t >= self.rewind["t0"]:
            u = (t - self.rewind["t0"]) / (self.rewind["end"] - self.rewind["t0"])
            done = done[:max(0, int(len(done) * (1 - u) + 0.999))] if u < 1 else []
        for r, a in enumerate(done):
            y = y0 + r * 50
            if y > 1520:
                break
            f.text(f"{a['v']:g} m/s", 150, y, 36, C["white"], "Bold", anchor="lm")
            if a["hit"]:
                hy = self.target[1] - 0.5 * G * a["t_end"] ** 2
                f.text(f"HIT at {hy:.1f} m", 930, y, 36, C["mint"], "Bold", anchor="rm")
            else:
                f.text("MISS: it landed first", 930, y, 36, C["pink"], "Bold", anchor="rm")

    def _particles(self, f, t):
        rng = np.random.default_rng(29)
        T_END = self.duration
        for i in range(26):
            x0, y0 = rng.uniform(40, 1040), rng.uniform(0, 1920)
            cyc, ph, r = rng.integers(1, 4), rng.uniform(0, 6.28), rng.uniform(1.5, 2.8)
            y = (y0 + 1920 * t / T_END) % 1920
            f.dot(x0 + 10 * math.sin(2 * math.pi * t / T_END + ph), y, r, C["mint"] if i % 3 else C["core"],
                  0.14 + 0.12 * math.sin(2 * math.pi * cyc * t / T_END + ph))

    def _key_times(self):
        ts = [0.0, 0.3]
        for a in self.acts:
            if a["type"] == "shot":
                ts += [a["fire"] + a["t_end"] * 0.5, a["fire"] + a["t_end"] + 0.1]
            else:
                ts.append(a["t0"] + 0.5)
        ts.append(self.duration - 1 / FPS)
        return sorted(set(round(x, 2) for x in ts if 0 <= x < self.duration))
