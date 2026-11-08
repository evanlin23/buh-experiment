"""Pacing metrics for Shorts: motion, headline/counter changes, sound events, dead stretches.

Usage: python -I tools/pacing.py "Label A" a.mp4 "Label B" b.mp4 ...
"""
import json, subprocess, sys
import numpy as np
from scipy.signal import find_peaks, stft
FPS, SR, W, H = 30, 22050, 90, 160
def frames(v):
    raw = subprocess.run(["ffmpeg","-v","error","-i",v,"-map","0:v:0","-vf",f"scale={W}:{H},format=gray","-f","rawvideo","-"],capture_output=True,check=True).stdout
    return np.frombuffer(raw,np.uint8).reshape(-1,H,W).astype(np.float32)
def onsets(v):
    raw = subprocess.run(["ffmpeg","-v","error","-i",v,"-map","0:a:0","-ac","1","-ar",str(SR),"-f","f32le","-"],capture_output=True,check=True).stdout
    a = np.frombuffer(raw,np.float32)
    f,t,Z = stft(a,fs=SR,nperseg=2048,noverlap=2048-256); L=np.log1p(100*np.abs(Z))
    fl = np.concatenate([[0],np.maximum(0,np.diff(L,axis=1)).sum(0)]); fl/=fl.max()
    med = np.convolve(fl,np.ones(43)/43,"same")
    p,_ = find_peaks(fl,height=med+0.06,distance=int(0.04*SR/256)); return t[p]
def longest_gap(times, dur):
    x = np.concatenate([[0], np.sort(times), [dur]]); g = np.diff(x); i = np.argmax(g)
    return float(g[i]), float(x[i])
rows = []
for label, v in zip(sys.argv[1::2], sys.argv[2::2]):
    F = frames(v); dur = len(F)/FPS
    d = np.concatenate([[0], np.abs(np.diff(F,axis=0)).mean((1,2))])
    text = F[:, int(H*0.04):int(H*0.25), :]                     # headline + counter band
    td = np.concatenate([[0], np.abs(np.diff(text,axis=0)).mean((1,2))])
    tp,_ = find_peaks(td, height=max(1.2, np.percentile(td,80)), distance=5)
    tt = tp/FPS
    on = onsets(v)
    still = d < 0.25                                             # essentially no motion
    run, best, start, bs = 0, 0, 0, 0
    for i, s in enumerate(still):
        if s:
            if run == 0: start = i
            run += 1
            if run > best: best, bs = run, start
        else: run = 0
    g_text, g_text_at = longest_gap(tt, dur)
    g_on, g_on_at = longest_gap(on, dur)
    rows.append(dict(video=label, dur=round(dur,1),
        first_motion_s=round(float(np.argmax(d[1:] > 0.25)+1)/FPS,2),
        first_text_change_s=round(float(tt[0]) if len(tt) else -1,2),
        text_changes_per_s=round(len(tt)/dur,2),
        longest_no_text_change_s=f"{g_text:.1f} (from {g_text_at:.1f}s)",
        sound_events_per_s=round(len(on)/dur,2),
        longest_silence_between_events_s=f"{g_on:.1f} (from {g_on_at:.1f}s)",
        motion_mean=round(float(d.mean()),2),
        still_share=f"{100*still.mean():.0f}%",
        longest_still_s=f"{best/FPS:.1f} (from {bs/FPS:.1f}s)"))
keys = list(rows[0])
w = [max(len(k), *(len(str(r[k])) for r in rows)) for k in keys]
for k in keys:
    print(f"{k:34s}" + "  ".join(f"{str(r[k]):>24s}" for r in rows))
