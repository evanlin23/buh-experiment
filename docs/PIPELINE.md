# @packedbuh pipeline: three Shorts a day

The goal is 21 Shorts a week, each one a distinct idea. Rendering is no longer the bottleneck: a spec goes to a checked, packaged upload in about 75 seconds. What takes the time is finding ideas and writing specs.

## The daily loop (per Short, about 30–40 minutes of human time)

| Step | Command / action | Time |
|---|---|---|
| 1. Pick a vetted idea | From the backlog: label OPEN or PROVEN-OPEN, every fact sourced | 2 min |
| 2. Write the spec | Copy the closest spec in `shorts/specs/` and edit it (format below) | 20–30 min |
| 3. Review | `python shorts/make.py shorts/specs/<slug>.json --review`, then look at `renders/<slug>/sheet.png` | 10 s |
| 4. Build | `python shorts/make.py shorts/specs/<slug>.json`. It must print PASS | ~75 s |
| 5. Watch once with sound | `renders/<slug>/video.mp4` | 1 min |
| 6. Upload | Paste from `renders/<slug>/upload.md`; use `cover.png` as the cover | 3 min |
| 7. Log it | Add `{slug, topic, published, url}` to `shorts/specs/published.json` | 1 min |

**Weekly:** run one market and fact check over about 25 candidate ideas (the agent brief in `research/idea-audit.md` is the template), and keep at least 10 vetted ideas in the backlog. On Sunday, write the next week's specs in a batch and render them all with one command:

```bash
python shorts/make.py shorts/specs/ --jobs 4
```

Specs that haven't changed are skipped, so rerunning it is cheap.

## Quality gate (`shorts/qa.py`, run automatically by make)

| Check | Rule | Why |
|---|---|---|
| First motion | ≤ 0.1 s | The swipe decision happens in the first second |
| Dead air | ≤ 1.1 s with no new sound, number or big motion | A long still payoff reads as "the Short is over" |
| Longest still stretch | ≤ 1.0 s | |
| Still frames | ≤ 30% | The reference hits run at 4–20% |
| Longest silence | ≤ 1.5 s | |
| Loop seam (mean pixel difference, last frame vs first) | ≤ 1.0 | The replay should look like one video |
| Loudness | −14 ± 1 LUFS | YouTube's playback reference |
| Length | 12–35 s | |

`make` also refuses to build a spec whose slug, title or topic duplicates another spec or anything already in `published.json`.

## House rules, built into the template

- Every number on screen and in the description is computed from the spec's formula. Labels come from the same numbers that size the drawings.
- Every sound is placed on its event: steps, landmark crossings, payoffs, the rewind.
- The video ends on the exact first frame, and the first step starts on frame 1.
- The watermark is `@packedbuh`. The audio is our own; never add library music.

## Spec format (`LadderShort`)

```jsonc
{
  "slug": "paper_12_folds",                  // unique; also the output folder
  "topic": "paper folding length",           // unique across all specs and published Shorts
  "unit": "length",                          // length | count | time | mass (picks the number formatting)
  "format": "count_exact",                   // optional: show exact integers for counts
  "bpm": 120,
  "quantity": {"formula": "pi*t/6*(2**n+4)*(2**n-1)", "params": {"t": 0.0001}},  // or "values": [...]
  "start": 1,                                // the loop opens on this step
  "hook": ["HOW LONG MUST PAPER BE", "TO FOLD IT 12 TIMES?"],
  "counter": ["{n} FOLD{S}", "needs {q} of paper"],   // {n} {S}/{s} plural, {q}, {q_exact}, plus custom "fields"
  "fields": {"clock": {"formula": "n*15*60", "unit": "time"}},   // optional extra counter values
  "ruler_min": 0.0001,                       // smallest ruler tick
  "column": {"width": 300, "color": "sky"},  // optional wide glowing column under the bar (water level, air...).
                                             // Use it whenever a ladder has markers but no true-size icons:
                                             // a thin bar alone reads as still frames and fails QA
  "camera": {"frame": [{"from": 5, "to": 7, "min": 0.42}]},      // optional: hold a wider view for these steps
  "acts": [
    {"type": "climb", "to": 12, "beats": 1, "pause_after": {"7": 1}, "final_rise_beats": 2,
     "callouts": {"6": "STILL FITS ON A4"}},
    {"type": "payoff", "headline": ["TALLER THAN", "THE BURJ KHALIFA"], "beats": 2},
    {"type": "card", "headline": ["...", "..."], "beats": 3, "compare": {"q": 1219, "label": "Toilet paper", "sub": "1.2 km"}},
    {"type": "climb", "to": 42, "beats": 0.25, "lead_beats": 0.5, "tail_beats": 0.75, "ruler": false, "headline": ["...", "..."]},
    {"type": "payoff", "headline": ["...", "..."], "beats": 2, "size": "big"},
    {"type": "rewind", "beats": 4, "hold_beats": 0.5}
  ],
  "marks": [
    {"icon": "burj", "x": 620},                // true-size icon (length unit only); see shorts/ladder.py LANDMARKS
    {"q": 3.844e8, "label": "The Moon", "sub": "384,400 km", "glyph": "moon"}   // marker; sub defaults to the formatted q
  ],
  "cover": {"t": 6.45},                      // cover frame (drawn with the hook headline)
  "package": {"title": "...", "alt_titles": [], "description": ["...", "{steps}", "..."],
              "steps": {"6": "still fits on A4"}, "step_format": "{n} folds: {q} ({note})",
              "question": "...", "hashtags": [], "pinned": "...", "tags": [], "tiktok": "...", "reels": "...", "sources": []}
}
```

### Timing guide

At 120 BPM one beat is 0.5 s.

| Element | Duration | Notes |
|---|---|---|
| `climb` step | 0.5 s at `beats: 1` | 0.125 s at `beats: 0.25` for the fast "race" acts |
| `payoff` | 1.0 s (`beats: 2`) | Don't go longer |
| `card` | 1.5 s (`beats: 3`) | Only with a moving comparison bar |
| `rewind` | 2.0 s (`beats: 4`) | |
| Whole Short | 14–20 s | |

Glyphs: `moon`, `sun`, `planet`, `star`, `mount`, `person`, `galaxy`, `line` (the default).

Steps can also be things rather than numbers: give `quantity.values` plus `quantity.labels` (and optionally `quantity.words`), then use `{label}` and `{word}` in the counter. Example: `ocean_glasses` steps through a bucket, a bathtub … all the oceans. Formulas may use `math` functions plus `min`, `max`, `abs` and `round`.

The backlog of vetted ideas lives in `research/backlog.md`.

## Formats: rotate them

Three templates, each with its own structure, motion and sound. Only the house brand is shared: the navy ground, the two-line headline, the @packedbuh mark. YouTube allows a consistent look; what it flags is content with little variation.

| Template (`"template"`) | Hit family | What it looks like | Sound | Example specs |
|---|---|---|---|---|
| `ladder` (default) | Scale shock | A bar or column climbs past true-size landmarks on a log-zoom camera | Pitch ladder on the beat | `paper_12_folds`, `ocean_glasses`, `sky_weight`, `iphone_stack`, `rumor_doubles` |
| `race` | Physics race / convergence | Balls race down ramps with exact frictionless physics, with a live timer and leaderboard; then a twist act (balls dropped from different heights all arrive together) | A click per fixed distance travelled (faster = more clicks), finish bells | `fastest_ramp` |
| `reveal` | Famous phenomenon | A random rule iterated a million times resolves into a shape: chaos game on a polygon, or an IFS such as the Barnsley fern | A pluck per early jump, panned to where it lands, then a granular shimmer; the shape spins by its own symmetry | `chaos_game`, `barnsley_fern` (draft) |

Rotation rules:
- Never post two Shorts of the same template back to back.
- At three a day, aim for one of each template every day, or for 50% ladder / 25% race / 25% reveal across the week while the race and reveal backlogs are thinner.
- Rotate the colour accent too. Ladder uses warm peach; race uses a multi-colour cast; reveal uses magenta or mint.

### `race` spec

```jsonc
{"template": "race", "hook": ["WHICH RAMP", "IS FASTEST?"], "tauto_label": "5 BALLS, 5 HEIGHTS, ONE CURVE",
 "race": {"r": 260, "seconds": 2.6, "A": [132, 590], "click_px": 55,       // cycloid arch radius, cycloid time, start point
          "curves": [{"kind": "straight|circle|dip|cycloid", "name": "CYCLOID", "color": "warm", "depth": 0.6}]},
 "acts": [{"type": "race"}, {"type": "payoff", "headline": [...], "beats": 2},
          {"type": "card", "headline": [...], "beats": 3, "replay": true},
          {"type": "tauto", "headline": [...], "balls": 5}, {"type": "payoff", "headline": [...], "size": "big"},
          {"type": "rewind", "beats": 4}]}
```

### `reveal` spec

```jsonc
{"template": "reveal", "color": "pink", "doublings": 20,
 "rule": {"type": "polygon", "corners": 3, "ratio": 0.5, "norepeat": false, "center": false},
 //   or {"type": "ifs", "maps": [[a, b, c, d, e, f, probability], ...]}
 "hook": [...], "hook_beats": 5, "counter_label": "JUMPS", "answer": [...], "payoff_beats": 2,
 "bonus": [{"rule": {...}, "lines": ["5 CORNERS", "JUMP 62% OF THE WAY"], "chord": "G2 D3 G3 B3 D4"}]}
```

## Staying on the right side of YouTube's "inauthentic content" rule at three a day

The rule targets uploads with little variation: the same situation with the same outcome, over and over. Three Shorts a day from one template is exactly what it looks for unless every upload is a distinct idea with its own payoff. To guard against that:

- `make` blocks repeated topics, titles and slugs.
- Rotate the hit families: scale shock, famous phenomenon, convergence, real-life sim.
- Rotate the three templates (see Formats above), and add more over time:
  - a rectangle/area view for the A4-doubling idea;
  - a flow or particle sim, for traffic waves.
- Don't publish near-identical follow-ups. The data shows they fall 10–100× anyway.
