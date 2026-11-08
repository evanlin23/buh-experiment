# buh-experiment: coded math/physics Shorts

Research and tooling for a YouTube Shorts channel in the "satisfying math/physics loop" niche:
20–30 s vertical videos, neon-on-dark, rendered from code, with every sound tied to an on-screen event.

## What's here

| Path | What it is |
|---|---|
| `docs/PIPELINE.md` | **Start here:** the 3-a-day workflow, the QA gate, and the spec format |
| `shorts/make.py` | Spec → video + cover + QA + upload packaging, in about 75 s |
| `shorts/specs/*.json` | One file per Short; `published.json` logs what's live |
| `shorts/ladder_short.py` | Format 1, `ladder`: a bar climbs past true-size landmarks |
| `shorts/race_short.py` | Format 2, `race`: balls race down ramps with exact physics |
| `shorts/reveal_short.py` | Format 3, `reveal`: a random rule iterated a million times reveals a shape |
| `shorts/engine.py` | Neon compositor, synth and mixer, parallel renderer |
| `shorts/ladder.py`, `shorts/units.py` | True-size landmark icons, log camera, number formatting |
| `shorts/qa.py`, `shorts/package.py` | The quality gate and the upload-kit generator |
| `research/` | Niche analysis, idea audit, pacing study |
| `tools/av_analyze.py`, `tools/pacing.py` | Measure any Short (yours or a competitor's) |
| `prototype/chaos_game_short.py` | The original standalone prototype, superseded by the `reveal` template |

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

ffmpeg must be on `PATH`. The prototype uses the Inter font from `/usr/share/fonts/opentype/inter/` and falls back to DejaVu Sans.

## Make a Short

```bash
.venv/bin/python shorts/make.py shorts/specs/paper_12_folds.json --review   # 10 s contact sheet
.venv/bin/python shorts/make.py shorts/specs/paper_12_folds.json            # full build, ~75 s on 4 cores
```

Output goes to `renders/<slug>/`: `video.mp4`, `cover.png`, `sheet.png`, `qa.json`, `upload.md`, `upload.json`. See `docs/PIPELINE.md`.

## Render the prototype

```bash
.venv/bin/python prototype/chaos_game_short.py renders/chaos_game.mp4 --handle @packedbuh
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
