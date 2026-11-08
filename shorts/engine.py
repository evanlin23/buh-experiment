"""Shared engine for beat-locked neon Shorts.

A scene supplies the math; the engine supplies the look and the sound:
  * Frame: antialiased neon strokes per colour, additive light with glow and bloom,
    crisp text on top, the reference Shorts' navy-violet ground.
  * Mixer: event-driven synth voices placed at exact sample positions, a short room
    reverb, and two-pass loudness normalisation to YouTube's -14 LUFS.
  * run(): renders frames straight into ffmpeg and muxes the audio.

A scene is any object with:
    duration: float                       seconds; frames = round(duration * FPS)
    audio(mix: Mixer) -> None             schedule every sound
    draw(f: Frame, t: float) -> None      draw the frame at time t
and run(scene_factory) handles the command line:
    python scene.py OUT.mp4 [--preview] [--stills DIR [--at T ...]] [--handle @name]
"""
import argparse
import json
import os
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.io import wavfile
from scipy.ndimage import gaussian_filter
from scipy.signal import fftconvolve, lfilter

FPS, SR = 30, 48000
FONT_DIR = "/usr/share/fonts/opentype/inter/"


def hexrgb(h):
    return np.array([int(h[i:i + 2], 16) for i in (1, 3, 5)], np.float32) / 255


# Sampled from the reference Shorts, plus two extra accents for multi-object scenes.
C = {k: hexrgb(v) for k, v in dict(
    bg_top="#100b2a", bg_bot="#09071c", glow="#1a1240",
    warm="#ffad6e", core="#fff6e6", lav="#ad9dfc", white="#ffffff", dim="#8f89b8",
    mint="#5fe0c8", pink="#ff7bb0", sky="#79b8ff", handle="#4a4570").items()}


def font(weight, px, S=1.0):
    try:
        return ImageFont.truetype(f"{FONT_DIR}Inter-{weight}.otf", max(8, int(px * S)))
    except OSError:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", max(8, int(px * S)))


def rgba(color, a=1.0):
    return tuple(int(255 * c) for c in color) + (int(255 * a),)


# ------------------------------------------------------------------ video
class Video:
    """Output geometry. All scene coordinates are in 1080x1920 'design pixels'."""

    def __init__(self, preview=False, handle="@packedbuh"):
        self.S = 0.5 if preview else 1.0
        self.W, self.H = int(1080 * self.S), int(1920 * self.S)
        self.handle = handle
        self._bg = None

    def background(self):
        if self._bg is None:
            S, W, H = self.S, self.W, self.H
            y = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
            bg = C["bg_top"] * (1 - y) + C["bg_bot"] * y
            yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
            rad = np.exp(-(((xx - 540 * S) / (520 * S)) ** 2 + ((yy - 960 * S) / (640 * S)) ** 2))
            bg = bg + rad[..., None] * C["glow"] * 0.5
            img = Image.new("L", (W, H), 0)
            d = ImageDraw.Draw(img)
            f = font("Medium", 26, S)
            d.text(((W - d.textlength(self.handle, font=f)) / 2, 1560 * S), self.handle, font=f, fill=255)
            self._bg = bg + (np.asarray(img, np.float32) / 255)[..., None] * C["handle"]
        return self._bg


# ------------------------------------------------------------------ frame
class Frame:
    """One frame. Strokes are light (they add and glow); text is ink (crisp, on top)."""
    SS = 2  # stroke supersampling

    def __init__(self, v: Video):
        self.v, self.S = v, v.S
        self.layers = {}           # colour key -> (Image L, Draw) at SS resolution
        self.extra = []            # (intensity array HxW, colour) e.g. particle density
        self.ink = Image.new("RGBA", (v.W, v.H), (0, 0, 0, 0))
        self.inkd = ImageDraw.Draw(self.ink)
        self.flash = 0.0           # 0..1 bloom boost for payoff hits
        self.bloom = 1.0

    # -- coordinates: design px -> supersampled px
    def _p(self, pts):
        k = self.S * self.SS
        return [(float(x) * k, float(y) * k) for x, y in pts]

    def _draw(self, color):
        key = tuple(np.round(color, 4))
        if key not in self.layers:
            im = Image.new("L", (self.v.W * self.SS, self.v.H * self.SS), 0)
            self.layers[key] = (im, ImageDraw.Draw(im), np.asarray(color, np.float32))
        return self.layers[key][1]

    # -- light
    def line(self, pts, color=C["warm"], width=4, a=1.0):
        if len(pts) >= 2 and a > 0:
            self._draw(color).line(self._p(pts), fill=int(255 * min(1, a)),
                                   width=max(1, int(width * self.S * self.SS)), joint="curve")

    def poly(self, pts, color=C["warm"], width=4, a=1.0, fill=0.0):
        if a <= 0:
            return
        d = self._draw(color)
        p = self._p(pts)
        if fill > 0:
            d.polygon(p, fill=int(255 * min(1, fill * a)))
        self.line(list(pts) + [pts[0]], color, width, a)

    def rect(self, x0, y0, x1, y1, color=C["warm"], width=4, a=1.0, fill=0.0):
        self.poly([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], color, width, a, fill)

    def circle(self, cx, cy, r, color=C["warm"], width=4, a=1.0, fill=0.0):
        if a <= 0 or r <= 0:
            return
        k = self.S * self.SS
        box = [(cx - r) * k, (cy - r) * k, (cx + r) * k, (cy + r) * k]
        d = self._draw(color)
        if fill > 0:
            d.ellipse(box, fill=int(255 * min(1, fill * a)))
        if width > 0:
            d.ellipse(box, outline=int(255 * min(1, a)), width=max(1, int(width * k)))

    def dot(self, cx, cy, r, color=C["core"], a=1.0):
        self.circle(cx, cy, r, color, width=0, a=a, fill=1.0)

    def intensity(self, I, color=C["warm"]):
        """Add a full-frame (H x W) float intensity image as light."""
        self.extra.append((I, np.asarray(color, np.float32)))

    # -- ink
    def text(self, s, x, y, px=60, color=C["white"], weight="ExtraBold", anchor="mt", a=1.0, spacing=0):
        if a <= 0:
            return
        f = font(weight, px, self.S)
        S = self.S
        if spacing:
            widths = [self.inkd.textlength(c, font=f) for c in s]
            total = sum(widths) + spacing * S * (len(s) - 1)
            cx = x * S - total / 2 if anchor[0] == "m" else x * S
            for c, w in zip(s, widths):
                self.inkd.text((cx, y * S), c, font=f, fill=rgba(color, a), anchor="l" + anchor[1])
                cx += w + spacing * S
        else:
            self.inkd.text((x * S, y * S), s, font=f, fill=rgba(color, a), anchor=anchor)

    def headline(self, l1, l2=None, y=130, px=62, a=1.0, l2px=None):
        """The two-line hook/answer block: white line, lavender line."""
        self.text(l1, 540, y, px, C["white"], a=a)
        if l2:
            self.text(l2, 540, y + px * 1.2, l2px or px, C["lav"], a=a)

    def counter(self, label, value, y=128, a=1.0, px=128):
        self.text(label, 540, y, 30, C["dim"], "SemiBold", a=a, spacing=7)
        self.text(value, 540, y + 44, px, C["white"], "Bold", a=a)

    def label(self, title, sub=None, x=0, y=0, a=1.0, anchor="lm", px=30, sub_color=C["mint"]):
        """Small object label like 'Burj Khalifa / 828 m'."""
        self.text(title, x, y, px, C["white"], "Bold", anchor=anchor, a=a)
        if sub:
            self.text(sub, x, y + px * 0.95, px * 0.8, sub_color, "SemiBold", anchor=anchor, a=a)

    # -- composite
    @staticmethod
    def _up(a, W, H):
        """Bilinear upsample an (h, w, 3) float image to (H, W, 3) using Pillow's C resize."""
        return np.stack([np.asarray(Image.fromarray(np.ascontiguousarray(a[..., c])).resize((W, H), Image.BILINEAR))
                         for c in range(3)], -1)

    @staticmethod
    def _mix(planes, cols):
        """Sum single-channel planes (n, h, w) tinted by cols (n, 3) in one matrix multiply."""
        n, h, w = planes.shape
        return (planes.reshape(n, -1).T @ cols).reshape(h, w, 3)

    _dither = None

    def render(self, rng):
        v, S = self.v, self.S
        W, H = v.W, v.H
        full, half, small, cols = [], [], [], []
        for im, _, col in self.layers.values():
            if im.getbbox() is None:
                continue
            i1 = im.reduce(self.SS)
            i2 = i1.reduce(2)
            full.append(np.asarray(i1))
            half.append(np.asarray(i2))
            small.append(np.asarray(i2.reduce(2)))
            cols.append(col / 255)
        for I, col in self.extra:
            h2 = I.reshape(H // 2, 2, W // 2, 2).mean((1, 3))
            full.append(I * 255)
            half.append(h2 * 255)
            small.append(h2.reshape(H // 4, 2, W // 4, 2).mean((1, 3)) * 255)
            cols.append(col / 255)
        bg = v.background()
        if cols:
            cm = np.array(cols, np.float32)
            stk = lambda planes: np.stack(planes).astype(np.float32, copy=False)
            light = self._mix(stk(full), cm)
            g1 = self._up(gaussian_filter(self._mix(stk(half), cm), (1.1 * S, 1.1 * S, 0)), W, H)
            sm = self._mix(stk(small), cm)
            bl = gaussian_filter(sm, (4, 4, 0)) * 1.2 + gaussian_filter(sm, (16, 16, 0)) * 0.9
            light = light * 1.6 + g1 * 1.1 + self._up(bl, W, H) * (self.bloom + 1.6 * self.flash)
            out = bg + (1 - bg) * (1 - np.exp(-light))     # additive light with soft roll-off to white
        else:
            out = bg.copy()
        box = self.ink.getbbox()
        if box:
            x0, y0, x1, y1 = box
            ink = np.asarray(self.ink.crop(box), np.float32) / 255
            al = ink[..., 3:]
            out[y0:y1, x0:x1] = out[y0:y1, x0:x1] * (1 - al) + ink[..., :3] * al
        if Frame._dither is None or Frame._dither.shape[1:3] != (H, W):
            Frame._dither = rng.uniform(-0.6 / 255, 0.6 / 255, (4, H, W, 1)).astype(np.float32)
        out += Frame._dither[rng.integers(4)]
        return (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)


# ------------------------------------------------------------------ music
NOTE = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
PENTA_D = {"D", "E", "F#", "A", "B"}


def midi(n):
    return NOTE[n[:-1]] + 12 * (int(n[-1]) + 1)


def hz(n):
    return 440.0 * 2 ** (((midi(n) if isinstance(n, str) else n) - 69) / 12)


def ladder(start="A2", n=21, scale=PENTA_D):
    """n consecutive scale notes upward from start (D-major pentatonic by default)."""
    out, m = [], midi(start)
    while len(out) < n:
        name = NAMES[m % 12]
        if name in scale:
            out.append(f"{name}{m // 12 - 1}")
        m += 1
    return out


class Mixer:
    def __init__(self, duration, seed=7):
        self.n = int(round(duration * SR))
        self.L, self.R = np.zeros(self.n), np.zeros(self.n)
        self.rng = np.random.default_rng(seed)

    def t(self, dur):
        return np.arange(int(dur * SR)) / SR

    def add(self, t, sig, gain=1.0, pan=0.0):
        i = int(round(t * SR))
        if i >= self.n or i < 0:
            return
        seg = sig[:self.n - i] * gain
        self.L[i:i + len(seg)] += seg * np.cos((pan + 1) * np.pi / 4) * 1.414
        self.R[i:i + len(seg)] += seg * np.sin((pan + 1) * np.pi / 4) * 1.414

    # -- voices
    def bell(self, f, dur=1.4):
        t = self.t(dur)
        s = sum(a * np.sin(2 * np.pi * f * k * t) * np.exp(-t * d)
                for k, a, d in ((1, 1, 2.6), (2, .32, 4.5), (3, .12, 7), (4.16, .07, 9), (5.43, .04, 12)))
        return s * (1 - np.exp(-t * 600))

    def pluck(self, f, dur=0.45, decay=9):
        t = self.t(dur)
        s = (np.sin(2 * np.pi * f * t) + .45 * np.sin(4 * np.pi * f * t) * np.exp(-t * 14)
             + .2 * np.sin(6 * np.pi * f * t) * np.exp(-t * 22))
        return s * np.exp(-t * decay) * (1 - np.exp(-t * 900))

    def grain(self, f, dur=0.09):
        t = self.t(dur)
        return np.sin(2 * np.pi * f * t) * np.sin(np.pi * t / dur) ** 2

    def tick(self, f=2200, dur=0.03):
        t = self.t(dur)
        return np.sin(2 * np.pi * f * t) * np.exp(-t * 160)

    def pad(self, notes, dur=3.0, attack=0.02, decay=1.0):
        t = self.t(dur)
        s = np.zeros_like(t)
        ns = notes.split() if isinstance(notes, str) else notes
        for n in ns:
            f = hz(n)
            for h in range(1, 6):
                s += np.sin(2 * np.pi * f * h * t + self.rng.uniform(0, 6.28)) / h ** 1.6 * np.exp(-t * (decay + .5 * h))
        return s * np.minimum(1, t / attack) / len(ns)

    def sub_drop(self, dur=1.4):
        t = self.t(dur)
        f = 42 + 34 * np.exp(-t * 6)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.6) * (1 - np.exp(-t * 300))

    def hp(self, x, a=0.985):
        return lfilter([1, -1], [1, -a], x)

    def noise(self, dur):
        return self.rng.standard_normal(int(dur * SR))

    def sweep(self, dur, f0, f1, curve=2.0):
        """Noise through a one-pole low-pass sweeping f0 -> f1 (a riser, or a fall)."""
        n = int(dur * SR)
        x = self.rng.standard_normal(n)
        out, z = np.empty(n), 0.0
        for i0 in range(0, n, 256):
            fc = f0 + (f1 - f0) * (i0 / n) ** curve
            a = np.exp(-2 * np.pi * fc / SR)
            seg, zf = lfilter([1 - a], [1, -a], x[i0:i0 + 256], zi=[z])
            out[i0:i0 + 256], z = seg, zf[0]
        return self.hp(out, 0.995)

    def burst(self, dur=1.5, decay=3.5):
        return self.hp(self.noise(dur), 0.8) * np.exp(-self.t(dur) * decay)

    def payoff(self, t, chord="D3 A3 D4 F#4 A4 E5", top="D6", gain=1.0):
        """The payoff hit: pad + sub drop + bell + noise burst."""
        self.add(t, self.pad(chord, 3.0), 0.55 * gain)
        self.add(t, self.sub_drop(), 0.55 * gain)
        self.add(t, self.bell(hz(top), 2.0), 0.22 * gain)
        self.add(t, self.burst(), 0.05 * gain, -0.3)
        self.add(t, self.burst(), 0.05 * gain, 0.3)

    # -- master
    def master(self, path, lufs=-14.0, wet=0.22):
        ir_t = self.t(1.4)
        for ch, seed in ((self.L, 1), (self.R, 2)):
            ir = np.random.default_rng(seed).standard_normal(len(ir_t)) * np.exp(-ir_t / 0.3)
            ir = lfilter([0.3], [1, -0.7], ir)
            ir /= np.sqrt((ir ** 2).sum())
            ch += fftconvolve(ch, ir)[:self.n] * wet
        mix = np.stack([self.L, self.R], 1)
        mix -= mix.mean(0)
        mix = np.tanh(1.4 * mix / (np.abs(mix).max() + 1e-9)) / np.tanh(1.4)
        fade = int(0.03 * SR)
        mix[-fade:] *= np.linspace(1, 0, fade)[:, None]
        raw = path + ".raw.wav"
        wavfile.write(raw, SR, mix.astype(np.float32))
        meas = subprocess.run(["ffmpeg", "-hide_banner", "-i", raw, "-af",
                               f"loudnorm=I={lufs}:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                              capture_output=True, text=True).stderr
        m = json.loads(meas[meas.rindex("{"):meas.rindex("}") + 1])
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-af",
                        f"loudnorm=I={lufs}:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
                        f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:linear=true",
                        "-ar", str(SR), path], check=True)
        os.remove(raw)


# ------------------------------------------------------------------ helpers
def ease(u):
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def ease_out(u):
    u = min(1.0, max(0.0, u))
    return 1 - (1 - u) ** 3


def lerp(a, b, u):
    return a + (b - a) * u


def fmt_int(n):
    return f"{int(n):,}"


# ------------------------------------------------------------------ render
DEFAULT_HANDLE = "@packedbuh"
_WORKER = {}


def _init_worker(make_scene, preview, handle):
    v = Video(preview, handle)
    _WORKER["v"], _WORKER["scene"] = v, make_scene(v)


def _render_index(k):
    f = Frame(_WORKER["v"])
    _WORKER["scene"].draw(f, k / FPS)
    return f.render(np.random.default_rng(k)).tobytes()


def render_stills(make_scene, out_dir, times=None, preview=False, handle=DEFAULT_HANDLE, headline=None):
    """Write PNG stills. Returns the list of paths."""
    v = Video(preview, handle)
    scene = make_scene(v)
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for t in times or getattr(scene, "key_times", [0.0]):
        f = Frame(v)
        if headline is not None and hasattr(scene, "draw_cover"):
            scene.draw_cover(f, t, headline)
        else:
            scene.draw(f, t)
        path = os.path.join(out_dir, f"t{t:05.2f}.png")
        Image.fromarray(f.render(np.random.default_rng(0))).save(path)
        paths.append(path)
    return paths


def render_video(make_scene, out, preview=False, handle=DEFAULT_HANDLE, jobs=None, log=print):
    """Render audio + all frames (in parallel worker processes) and mux to an mp4."""
    import multiprocessing as mp
    jobs = jobs or max(1, (os.cpu_count() or 2))
    v = Video(preview, handle)
    scene = make_scene(v)
    nframes = int(round(scene.duration * FPS))
    with tempfile.TemporaryDirectory() as tmp:
        wav = os.path.join(tmp, "audio.wav")
        mix = Mixer(scene.duration)
        scene.audio(mix)
        mix.master(wav)
        enc = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{v.W}x{v.H}",
             "-r", str(FPS), "-i", "-", "-i", wav, "-c:v", "libx264", "-preset", "medium", "-crf", "17",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart",
             out], stdin=subprocess.PIPE)
        ctx = mp.get_context("fork")
        with ctx.Pool(jobs, initializer=_init_worker, initargs=(make_scene, preview, handle)) as pool:
            for k, buf in enumerate(pool.imap(_render_index, range(nframes), chunksize=4)):
                enc.stdin.write(buf)
                if log and k % 150 == 0:
                    log(f"  frame {k}/{nframes}")
        enc.stdin.close()
        if enc.wait() != 0:
            raise RuntimeError("ffmpeg failed")
    return dict(frames=nframes, duration=scene.duration, size=(v.W, v.H))


def run(make_scene):
    """Command line for a single hand-written scene file."""
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--preview", action="store_true", help="render at 540x960 (faster)")
    ap.add_argument("--stills", help="write key frames as PNGs into this directory and exit")
    ap.add_argument("--at", type=float, nargs="*", help="times for --stills (default: scene.key_times)")
    ap.add_argument("--handle", default=DEFAULT_HANDLE)
    ap.add_argument("--jobs", type=int, default=None)
    args = ap.parse_args()
    if args.stills:
        render_stills(make_scene, args.stills, args.at, args.preview, args.handle)
        return
    info = render_video(make_scene, args.out, args.preview, args.handle, args.jobs)
    print("wrote", args.out, f"({info['frames']} frames, {info['duration']:.2f}s)")
