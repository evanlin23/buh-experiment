"""Sound for the Never Sleep proof: paper foley on every cue the scene exports, plus a small lullaby bed.

Usage (called by render.cjs): python -I never_sleep_audio.py CUES.json OUT.wav

Every effect is placed on a cue time read from the scene's own timeline (window.CUES),
so a sound can't drift from the pixel event that causes it.
"""
import json
import os
import subprocess
import sys

import numpy as np
from scipy.signal import butter, lfilter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "shorts"))
from engine import SR, Mixer, hz  # noqa: E402


def band(x, lo, hi, order=2):
    b, a = butter(order, [lo / (SR / 2), hi / (SR / 2)], btype="band")
    return lfilter(b, a, x)


def low(x, fc, order=2):
    b, a = butter(order, fc / (SR / 2))
    return lfilter(b, a, x)


def env(n, attack=0.002, decay=30.0):
    t = np.arange(n) / SR
    return np.minimum(1, t / attack) * np.exp(-t * decay)


def main(cues_path, out):
    spec = json.load(open(cues_path))
    dur, off = spec["duration"], spec["offset"]
    m = Mixer(dur + 0.5, seed=11)
    rng = np.random.default_rng(5)
    sec = lambda s: int(s * SR)

    def paper_tab(gain=1.0):
        n = sec(0.06)
        click = band(m.noise(n / SR), 2500 + rng.uniform(-400, 600), 7000) * env(n, decay=70)
        tock = np.sin(2 * np.pi * rng.uniform(190, 260) * np.arange(n) / SR) * env(n, decay=55)
        return (click * 0.9 + tock * 0.35) * gain

    def swish(d, lo, hi, gain):
        n = sec(d)
        x = band(m.noise(d), lo, hi) * np.sin(np.pi * np.arange(n) / n) ** 1.5
        return x * gain

    def thud(f=95, d=0.18, gain=1.0):
        n = sec(d)
        t = np.arange(n) / SR
        return (np.sin(2 * np.pi * f * t) * env(n, decay=22) + 0.3 * band(m.noise(d), 600, 3000) * env(n, decay=60)) * gain

    def scratch(d):
        n = sec(d)
        t = np.arange(n) / SR
        am = 0.55 + 0.45 * np.sin(2 * np.pi * 13 * t) ** 2
        return band(m.noise(d), 2200, 6500) * am * np.sin(np.pi * t / d) ** 0.7

    fill_notes = ["F4", "G4", "A4", "C5", "D5"]
    for c in spec["cues"]:
        t = c["t"] - off
        if t < -0.2 or t > dur:
            continue
        k = c["type"]
        pan = float(rng.uniform(-0.25, 0.25))
        if k == "pop":
            m.add(t, paper_tab(0.55 if c.get("soft") else 0.8), 0.5, pan)
        elif k == "clocktick":
            m.add(t, m.tick(3400 if int(t * 4) % 2 else 2700, 0.025), 0.09, 0.35)
        elif k == "clunk":
            m.add(t, thud(140, 0.15), 0.35, 0.35)
            m.add(t, m.bell(hz("C6"), 0.6), 0.05, 0.35)
        elif k == "fold":
            m.add(t, swish(0.35, 900, 5000, 0.35), 1.0, 0.0)
        elif k == "flap":
            m.add(t, swish(0.14, 300, 2600, 0.6), 1.0, pan)
            m.add(t + 0.02, thud(110, 0.1, 0.4), 1.0, pan)
        elif k == "tick":
            m.add(t, m.tick(2500 + rng.uniform(-150, 150), 0.02), 0.05, -0.55)
        elif k == "whoosh":
            m.add(t, low(m.sweep(0.95, 400, 4200, 1.2), 6000), 0.22, -0.2)
            m.add(t, swish(0.9, 200, 1800, 0.3), 1.0, 0.2)
        elif k == "stamp":
            m.add(t, thud(85 if c.get("soft") else 70, 0.16, 0.6 if c.get("soft") else 1.0), 0.45, pan)
        elif k == "draw":
            m.add(t, scratch(c.get("dur", 1.0)), 0.18, -0.3)
        elif k == "grow":
            d = c.get("dur", 0.9)
            m.add(t, m.sweep(d, 300, 2600, 1.6), 0.12, 0.3)
        elif k == "slide":
            m.add(t, swish(0.55, 250, 2200, 0.55), 1.0, 0.1)
        elif k == "fill":
            i = c["i"]
            note = fill_notes[i % 5][:-1] + str(int(fill_notes[i % 5][-1]) + i // 10)
            m.add(t, m.pluck(hz(note), 0.5, 11), 0.16, -0.4 + 0.8 * (i % 10) / 9)
        elif k == "chime":
            m.add(t, m.pad("F3 C4 F4 A4 C5", 2.4, 0.01, 1.2), 0.35)
            m.add(t, m.bell(hz("F6"), 2.2), 0.12, 0.2)
            m.add(t, m.bell(hz("C6"), 2.0), 0.08, -0.2)

    # Bed: a music-box lullaby in the bedroom, a plucked figure on the riso page, both at 80 BPM.
    beat = 0.75
    turn = next(c["t"] for c in spec["cues"] if c["type"] == "whoosh") - off
    lull = ["A5", "C6", "F5", "E5", "D5", "C5", "A4", "C5"]
    b = 0
    while b * beat < turn + 0.2:
        t = b * beat
        m.add(t, m.bell(hz(lull[b % len(lull)]), 1.6), 0.075 * min(1, t / 0.6 + 0.35), 0.15)
        if b % 4 == 0:
            m.add(t, m.pad("F2 C3 A3" if (b // 4) % 2 == 0 else "D2 A2 F3", 3.2, 0.4, 0.5), 0.12)
        b += 1
    chords = ["D3 F3 A3", "A#2 D3 F3", "F3 A3 C4", "C3 E3 G3"]
    arp = [0, 1, 2, 1]
    b = 0
    while turn + 0.6 + b * beat / 2 < dur:
        t = turn + 0.6 + b * beat / 2
        ch = chords[(b // 8) % 4].split()
        m.add(t, m.pluck(hz(ch[arp[b % 4]][:-1] + str(int(ch[arp[b % 4]][-1]) + 2)), 0.4, 10), 0.05, 0.25 * np.sin(b))
        if b % 8 == 0:
            m.add(t, m.pad(" ".join(ch), 3.2, 0.3, 0.6), 0.1)
        b += 1
    room = low(m.noise(dur + 0.5), 500) * 0.004
    m.L += room
    m.R += room[::-1]

    vo = next((c for c in spec["cues"] if c["type"] == "vo"), None)
    if vo:
        # Narration on top: the bed and foley sit 18 dB under the voice (RMS) and duck a further ~5 dB while it speaks.
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), vo["src"])
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                             capture_output=True, check=True).stdout
        v = np.frombuffer(raw, np.float32).astype(np.float64)
        i0 = int(round((vo["t"] - off) * SR))
        v = v[:max(0, m.n - i0)]
        ev = low(np.abs(v), 5)
        ev = np.clip(ev / (np.percentile(ev, 95) + 1e-9), 0, 1)
        vo_env = np.zeros(m.n)
        vo_env[i0:i0 + len(ev)] = ev
        bed = np.sqrt(np.mean(((m.L + m.R) / 2) ** 2)) + 1e-12
        speech = np.sqrt(np.mean(v[ev > 0.25] ** 2))
        g = speech * 10 ** (-18 / 20) / bed
        duck = g * (1 - 0.45 * vo_env)
        m.L *= duck
        m.R *= duck
        m.L[i0:i0 + len(v)] += v
        m.R[i0:i0 + len(v)] += v
    m.master(out, wet=0.12 if vo else 0.18)


if __name__ == "__main__":
    main(*sys.argv[1:3])
