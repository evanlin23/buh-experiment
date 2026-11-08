"""Audio/visual sync analysis for a short video.

Usage: python -I av_analyze.py <video.mp4> <out_prefix> <label>
Writes <out_prefix>_timeline.png and <out_prefix>_onsets.json, prints a summary.
"""
import json
import subprocess
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.signal import find_peaks, stft

video, prefix, label = sys.argv[1], sys.argv[2], sys.argv[3]
SR = 22050
FPS = 30
W, H = 90, 160

# ---- audio ----
raw = subprocess.run(
    ["ffmpeg", "-v", "error", "-i", video, "-map", "0:a:0", "-ac", "1", "-ar", str(SR),
     "-f", "f32le", "-"], capture_output=True, check=True).stdout
a = np.frombuffer(raw, dtype=np.float32)
dur = len(a) / SR

hop = 256
f, t, Z = stft(a, fs=SR, nperseg=2048, noverlap=2048 - hop)
mag = np.abs(Z)
logmag = np.log1p(100 * mag)
flux = np.maximum(0, np.diff(logmag, axis=1)).sum(axis=0)
flux = np.concatenate([[0], flux])
flux /= flux.max() + 1e-9
rms = np.sqrt(np.convolve(a ** 2, np.ones(hop) / hop, mode="same"))[::hop][: len(t)]

# adaptive threshold onset picking
med = np.convolve(flux, np.ones(43) / 43, mode="same")
peaks, _ = find_peaks(flux, height=med + 0.06, distance=int(0.04 * SR / hop))
onsets = t[peaks]

NOTE = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
def note_name(freq):
    if freq <= 0:
        return "-"
    m = int(round(69 + 12 * np.log2(freq / 440.0)))
    return f"{NOTE[m % 12]}{m // 12 - 1}"

# dominant pitch shortly after each onset (60-1500 Hz band)
band = (f > 60) & (f < 1500)
pitches = []
for p in peaks:
    seg = mag[band, p: p + 6].mean(axis=1)
    pitches.append(float(f[band][np.argmax(seg)]))

# spectral centroid over time (proxy for brightness / pitch rise)
centroid = (f[:, None] * mag).sum(0) / (mag.sum(0) + 1e-9)

# ---- video ----
raw_v = subprocess.run(
    ["ffmpeg", "-v", "error", "-i", video, "-map", "0:v:0", "-vf", f"scale={W}:{H},format=gray",
     "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
frames = np.frombuffer(raw_v, dtype=np.uint8).reshape(-1, H, W).astype(np.float32)
vt = np.arange(len(frames)) / FPS
diff = np.concatenate([[0], np.abs(np.diff(frames, axis=0)).mean(axis=(1, 2))])
bright = frames.mean(axis=(1, 2))
# top band (counter text region ~ top 15%) change: detects counter ticks
top = frames[:, int(H * 0.03): int(H * 0.16), :]
topdiff = np.concatenate([[0], np.abs(np.diff(top, axis=0)).mean(axis=(1, 2))])
tpk, _ = find_peaks(topdiff, height=max(1.5, np.percentile(topdiff, 90)), distance=6)
ticks = vt[tpk]

# ---- sync: lag between audio flux and visual diff ----
af = np.interp(vt, t, flux)
vd = (diff - diff.mean()) / (diff.std() + 1e-9)
afz = (af - af.mean()) / (af.std() + 1e-9)
lags = np.arange(-15, 16)
xc = [np.corrcoef(np.roll(afz, k), vd)[0, 1] for k in lags]
best = int(lags[int(np.argmax(xc))])

# onset -> nearest counter tick
match = []
for tk in ticks:
    if len(onsets):
        d = onsets - tk
        j = int(np.argmin(np.abs(d)))
        match.append(float(d[j]))

# first/last frame similarity (loop seam)
seam = float(np.abs(frames[0] - frames[-1]).mean())
seam_mid = float(np.abs(frames[0] - frames[len(frames) // 2]).mean())

ioi = np.diff(onsets) if len(onsets) > 1 else np.array([0.0])
summary = {
    "label": label,
    "duration_s": round(dur, 2),
    "integrated_rms_dbfs": round(20 * np.log10(np.sqrt((a ** 2).mean()) + 1e-12), 1),
    "peak_dbfs": round(20 * np.log10(np.abs(a).max() + 1e-12), 1),
    "n_onsets": int(len(onsets)),
    "onsets_per_s_by_third": [int(((onsets >= dur * k / 3) & (onsets < dur * (k + 1) / 3)).sum())
                              for k in range(3)],
    "median_ioi_s": round(float(np.median(ioi)), 3),
    "n_counter_ticks": int(len(ticks)),
    "counter_tick_times": [round(float(x), 2) for x in ticks],
    "tick_to_nearest_onset_ms": [round(1000 * x) for x in match],
    "av_best_lag_frames(+ = audio later)": best,
    "av_xcorr_at_best": round(float(max(xc)), 3),
    "loop_seam_diff_first_vs_last": round(seam, 2),
    "first_vs_mid_diff": round(seam_mid, 2),
    "first_20_onsets": [[round(float(o), 2), note_name(p)] for o, p in zip(onsets[:20], pitches[:20])],
}
json.dump({**summary, "onsets": [float(x) for x in onsets], "pitches_hz": pitches},
          open(prefix + "_onsets.json", "w"), indent=1, default=float)
print(json.dumps(summary, indent=1, default=float))

# ---- plot ----
fig, ax = plt.subplots(4, 1, figsize=(14, 9), sharex=True)
ax[0].imshow(logmag[:400], origin="lower", aspect="auto", extent=[t[0], t[-1], 0, f[399]], cmap="magma")
ax[0].set_ylabel("Hz"); ax[0].set_title(f"{label}: spectrogram (0-{int(f[399])} Hz)")
ax[1].plot(t, flux, lw=0.6, color="tab:orange", label="audio onset strength")
ax[1].vlines(onsets, 0, 1, color="k", lw=0.3, alpha=0.5)
ax[1].legend(loc="upper left", fontsize=8)
ax[2].plot(vt, diff, lw=0.7, color="tab:blue", label="visual frame change")
ax[2].plot(vt, topdiff, lw=0.7, color="tab:green", label="counter-region change")
ax[2].vlines(ticks, 0, max(diff.max(), topdiff.max()), color="tab:green", lw=0.4, alpha=0.6)
ax[2].legend(loc="upper left", fontsize=8)
ax[3].plot(vt, bright, color="tab:purple", lw=0.8, label="frame brightness")
ax3b = ax[3].twinx(); ax3b.plot(t, centroid, color="tab:red", lw=0.4, alpha=0.6, label="spectral centroid")
ax[3].legend(loc="upper left", fontsize=8); ax3b.legend(loc="upper right", fontsize=8)
ax[3].set_xlabel("seconds")
plt.tight_layout(); plt.savefig(prefix + "_timeline.png", dpi=80)
