"""Automated QA for a rendered Short: pacing, dead air, loop seam, loudness.

The thresholds come from measuring the reference hits (MathMango 25.7M, the dragon
and mirror Shorts at 1.9M) and from the house rule that no stretch may look or sound
like the video has ended.
"""
import json
import re
import subprocess

import numpy as np
from scipy.signal import find_peaks, stft

FPS, SR, W, H = 30, 22050, 90, 160

RULES = {                       # metric: (min, max)
    "duration_s": (12.0, 35.0),
    "first_motion_s": (None, 0.1),
    "still_share": (None, 0.30),
    "longest_still_s": (None, 1.0),
    "dead_air_s": (None, 1.1),
    "longest_silence_s": (None, 1.5),
    "loop_seam": (None, 1.0),
    "lufs": (-15.0, -13.0),
}


def _frames(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-map", "0:v:0", "-vf",
                          f"scale={W}:{H},format=gray", "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype(np.float32)


def _onsets(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-map", "0:a:0", "-ac", "1", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.float32)
    _, t, Z = stft(a, fs=SR, nperseg=2048, noverlap=2048 - 256)
    L = np.log1p(100 * np.abs(Z))
    fl = np.concatenate([[0], np.maximum(0, np.diff(L, axis=1)).sum(0)])
    fl /= fl.max() + 1e-9
    med = np.convolve(fl, np.ones(43) / 43, "same")
    p, _ = find_peaks(fl, height=med + 0.06, distance=int(0.04 * SR / 256))
    return t[p]


def _lufs(path):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "ebur128=peak=true",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    summary = err[err.rfind("Summary:"):]
    m = re.search(r"I:\s+(-?[\d.]+) LUFS", summary)
    p = re.search(r"Peak:\s+(-?[\d.]+) dBFS", summary)
    return (float(m.group(1)) if m else None), (float(p.group(1)) if p else None)


def _longest_gap(times, dur):
    x = np.concatenate([[0.0], np.sort(times), [dur]])
    g = np.diff(x)
    i = int(np.argmax(g))
    return float(g[i]), float(x[i])


def measure(path):
    F = _frames(path)
    dur = len(F) / FPS
    d = np.concatenate([[0], np.abs(np.diff(F, axis=0)).mean((1, 2))])
    band = F[:, int(H * 0.04):int(H * 0.25), :]          # headline + counter
    td = np.concatenate([[0], np.abs(np.diff(band, axis=0)).mean((1, 2))])
    tp, _ = find_peaks(td, height=max(1.2, np.percentile(td, 80)), distance=5)
    text_t = tp / FPS
    on = _onsets(path)
    still = d < 0.25
    best = run = 0
    for s in still:
        run = run + 1 if s else 0
        best = max(best, run)
    events = np.concatenate([on, text_t, np.nonzero(d > np.percentile(d, 90))[0] / FPS])
    dead, dead_at = _longest_gap(events, dur)
    sil, sil_at = _longest_gap(on, dur)
    lufs, peak = _lufs(path)
    moving = np.nonzero(d[1:] > 0.25)[0]
    return dict(
        duration_s=round(dur, 2),
        first_motion_s=round(float(moving[0] + 1) / FPS, 3) if len(moving) else dur,
        still_share=round(float(still.mean()), 3),
        longest_still_s=round(best / FPS, 2),
        dead_air_s=round(dead, 2), dead_air_at=round(dead_at, 2),
        longest_silence_s=round(sil, 2), longest_silence_at=round(sil_at, 2),
        sound_events_per_s=round(len(on) / dur, 2),
        text_changes_per_s=round(len(text_t) / dur, 2),
        loop_seam=round(float(np.abs(F[0] - F[-1]).mean()), 2),
        lufs=lufs, true_peak_dbfs=peak,
    )


def check(metrics, rules=RULES):
    rows, ok = [], True
    for k, (lo, hi) in rules.items():
        v = metrics.get(k)
        good = v is not None and (lo is None or v >= lo) and (hi is None or v <= hi)
        ok &= good
        rows.append(dict(metric=k, value=v, min=lo, max=hi, ok=good))
    return ok, rows


def run(path, out_json=None):
    m = measure(path)
    ok, rows = check(m)
    res = dict(ok=ok, metrics=m, checks=rows)
    if out_json:
        with open(out_json, "w") as fh:
            json.dump(res, fh, indent=1)
    return res


if __name__ == "__main__":
    import sys
    for p in sys.argv[1:]:
        r = run(p)
        print(("PASS " if r["ok"] else "FAIL ") + p)
        for c in r["checks"]:
            print(f"  {'ok ' if c['ok'] else 'BAD'} {c['metric']:18s} {c['value']}  (min {c['min']}, max {c['max']})")
