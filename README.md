# buh-experiment: coded math/physics Shorts

Research and tooling for a YouTube Shorts channel in the "satisfying math/physics loop" niche:
20–30 s vertical videos, neon-on-dark, rendered from code, with every sound tied to an on-screen event.

## What's here

| Path | What it is |
|---|---|
| `research/niche-analysis.md` | Findings: how the 1M+ hits are built, the market, the idea slate |
| `tools/av_analyze.py` | Measures any Short: audio onsets vs. on-screen counter ticks, tempo, pitch, loop seam |
| `prototype/chaos_game_short.py` | A complete Short rendered from code: the chaos game → Sierpinski triangle |

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

ffmpeg must be on `PATH`. The prototype uses the Inter font from `/usr/share/fonts/opentype/inter/` and falls back to DejaVu Sans.

## Render the prototype

```bash
.venv/bin/python prototype/chaos_game_short.py renders/chaos_game.mp4 --handle @yourchannel
```

- `--preview` renders at 540×960, about 4× faster.
- `--stills DIR` writes PNGs of the key moments and exits.

A full 1080×1920 render takes about 2 minutes on a laptop-class CPU.

How it's built:

- One schedule drives both the frames and the audio. Every pluck is placed at the exact sample of the frame where its dot lands.
- The jump count doubles on every beat of a 120 BPM grid, with each beat exactly 15 frames.
- The beat notes climb a D-major pentatonic ladder.
- The payoff resolves on D. The rewind plays the ladder backwards and ends on the exact first frame, so the video loops cleanly.
- Audio is normalised to −14 LUFS, YouTube's playback reference.

## Analyse a Short

```bash
.venv/bin/python tools/av_analyze.py some_short.mp4 out/some_short "Label"
```

Prints a JSON summary and writes `out/some_short_timeline.png`, a spectrogram over onset strength, visual change and counter-region change. The summary includes:

- tempo and median gap between notes
- how far each on-screen counter tick sits from the nearest audio onset, in ms
- how closely the last frame matches the first (loop seam)
