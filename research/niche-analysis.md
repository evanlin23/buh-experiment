# Million-view math Shorts: research notes (8 Nov 2026)

Sources:
- Frame and audio measurements: the three uploaded hits, measured with `tools/av_analyze.py`.
- View counts: the Return YouTube Dislike API (which mirrors YouTube's counts) and channel pages, fetched 8 Nov 2026.
- Upload dates: vidIQ.

## Key findings

1. **The topic picks the hit.**
   - MathMango posts one Short a day in a single template: same look, sound and structure. Its 25 Shorts range from 24K to 25.7M views.
   - All 5 of its 1M+ Shorts were famous facts before they were animated, and each has a one-number answer: 42 folds, π from clacks, 1.3 million Earths, infinite chocolate, cuts to an atom.
   - Its lesser-known puzzles (100 prisoners, coin rotation, block overhang) stall at 24K–820K.
2. **Paper folding/cutting is the strongest topic.** Six 1M+ Shorts from four channels in five weeks, 47.6M views combined. Each one added a twist: Moon → dragon curve → 15 folds. Straight copies of the Moon fold sit under 15K (about 25 of them).
3. **Remaking your own hit usually fails.**
   - "How Thin Is Paper After 42 Folds?" got 232K.
   - Play Paloooozaaaa's four remakes of its balls-and-mirrors hit got 48K–129K.
   - Exception: "I Folded It 15 Times This Time" got 2.3M.
4. **These don't predict a hit:**
   - Question titles: 24 of MathMango's 25 Shorts are questions.
   - Like rate: about 1% on hits and misses alike.
   - Doubling on its own: "What If One Cell Kept Doubling?" got 119K.
5. **Hit rate for a strong channel is about 20%.** That's 5 of 25 for MathMango and 3 of 16 math Shorts for Play Paloooozaaaa. Hits clear 1M within about 1–3 weeks.

## The template (measured)

| | Folds to the Moon (MathMango, 25.7M) | Dragon curve (Play Paloooozaaaa, 1.9M) | 1,024 balls (Play Paloooozaaaa, 1.9M) |
|---|---|---|---|
| Length | 30.8 s | 23.1 s | 26.0 s |
| Beat grid | 0.50 s per fold (120.2 BPM) | 1.00 s per fold, rewind 0.50 s | 2.00 s per doubling |
| Counter tick → note | steps every 0.50 s, matching the 0.499 s beat | median 9 ms | 5–36 ms |
| Pitch | pluck arpeggio over D bass | D-major pentatonic, one rung per fold; rewind reverses it and ends on D3 | a note on every bounce; landing thump grows 5 dB over the trips |
| Payoff at | 20.5 s (67%) | 10.5 s (45%) | 22.0 s (85%) |
| Loop seam (first vs last frame, 0–255) | 1.59 | 1.10 | 0.29 |

For scale on the loop seam: each video's first frame differs from its midpoint by 11–32.

**Structure:**
1. Hook question on frame 1.
2. Doubling ladder locked to the beat.
3. Payoff that replaces the headline.
4. Optional bonus.
5. Rewind back to the exact first frame.

**Visuals:**
- No voiceover.
- Navy-violet ground, `#100b2a` fading to `#09071c`, with a peach glow.
- Lavender (`#ad9dfc`) for the second line of the headline.
- Everything stays inside the center safe zone.
- No custom thumbnails.

**Descriptions:** they work through the math with real numbers and end with one comment prompt.

**The top hit has a bug.** In the folds video, each landmark label lags one drawing behind: the Leaning Tower of Pisa is labeled "House 10 m", the Eiffel Tower is labeled "Tower of Pisa 57 m", and the Eiffel Tower never gets its own label.

## MathMango, every Short

| Title | Views | Uploaded |
|---|---:|---|
| How Many Folds To Reach The Moon? | 25,694,219 | Oct 20 |
| How Many Clacks? | 10,816,519 | Oct 14 |
| How Many Cuts To Reach An Atom? | 5,030,031 | Oct 22 |
| Can You Get Infinite Chocolate? | 2,570,738 | Oct 26 |
| How Many Earths Fit Inside The Sun? | 1,290,636 | Oct 25 |
| Will They Ever Crash? | 819,554 | Oct 13 |
| Which Slide Is Fastest? | 658,852 | Oct 16 |
| Will The DVD Logo Ever Hit The Corner? | 599,896 | Oct 24 |
| How Far Can the Blocks Lean? | 556,000 | Oct 19 |
| How Much Money Reaches SPACE? | 416,379 | Oct 28 |
| How Many Balloons To Lift A House? | 266,577 | Nov 2 |
| How Many SPINS Does A Coin Make Around A Coin? | 256,330 | Oct 29 |
| How Thin Is Paper After 42 Folds? | 231,747 | Nov 6 |
| Will 1,000 Balls Stay Together? | 216,038 | Oct 17 |
| How Rare Is A Lottery Jackpot? | 213,442 | Oct 23 |
| How Big Is a Box of Every Human? | 175,356 | Oct 27 |
| Is a Coin Flip Really 50/50? | 173,209 | Oct 28 |
| Can All 100 People Find Their Number? | 121,536 | Oct 21 |
| This Simple Puzzle Takes Longer Than the Universe | 121,270 | Nov 5 |
| What If One Cell Kept Doubling? | 119,257 | Nov 4 |
| Will They All Come Back Together? | 113,342 | Oct 15 |
| Will They Ever Catch Up? | 103,466 | Oct 18 |
| How Hard To Throw A Ball So It NEVER Comes Down? | 102,375 | Nov 1 |
| Will They Reach the Bottom Together? | 55,877 | Oct 12 |
| How Heavy Is A Cloud? | 24,442 | Nov 3 |

## Hit families across the niche (2026, 1M+)

| Family | Examples |
|---|---|
| Scale shock: everyday object → absurd endpoint | Folds to the Moon 25.7M · Fold Paper 42 Times (Oddly Bouncy) 7.3M · Cuts to an atom 5.0M · Earths in the Sun 1.3M · Growing a hole to eat the Earth 1.1M |
| Famous phenomenon, shown | Clacks 10.8M · Fold a strip, unfold it (MathMellow) 5.4M · Infinite chocolate 2.6M · 15 folds 2.3M · Dragon curve 1.9M |
| Everything converges | Fabric of spacetime (particlesflow) 4.1M · 1,024 balls, two mirrors 1.9M |
| Real-life question, simulated | 100m Olympic winners in one race 3.0M · Rock paper scissors 2.3M · Fastest way to board a plane 1.2M · Why planes fly a curve 1.07M |
| The sound is the hook | "Which song is the ball playing?" (bouncyball, 2.5–7.0M each) · Graph says meow 6.9M · Famous flags sound insane 6.6M |

The first-wave ball sims hold the biggest numbers (11M–86M), but most predate 2026. Those channels' recent medians are 30–60K.

## Market and money

- **Copycats:** 10+ copycat channels started Aug–Oct 2026.
- **Shorts ad revenue gate (from 1 Feb 2027):** a channel earns Shorts ad revenue only in months with 10M+ qualified Shorts views over the past 90 days.
- **Payout:** an estimated $30–100 per million engaged views. Education long-form pays about 100× more per view.
- **TikTok:** Creator Rewards pays only for videos over 1 minute.
- **Policy risk:** the risk is "inauthentic content": templated uploads with little variation, judged across the whole channel. Animation rendered from code needs no AI label. The safeguard is one distinct idea and one payoff per Short.

## Ideas (first three = make first)

1. How long must paper be to fold it 12 times? → 1.2 km (Britney Gallivan, 2002). Gallivan's formula L = πt/6·(2ⁿ+4)(2ⁿ−1).
2. 1 grain on the first chessboard square, doubled every square → 2⁶⁴−1 grains, about 1,000 years of the world's wheat harvest.
3. Where did the square go? (missing-square puzzle) → the "triangle's" long edge bends, hiding one square.
4. Has anyone ever shuffled this deck? → 52! ≈ 8×10⁶⁷ orders.
5. Pick any number: why do they all fall to 1? (Collatz) → every number checked past 10²⁰ ends in 4 → 2 → 1, and nobody can prove they all do.
6. How many ancestors do you have? → 2⁴⁰ ≈ 1.1 trillion 40 generations back, against about 117 billion humans ever born.
7. Jump halfway to a random corner, 1,000,000 times → Sierpinski triangle (rendered: `prototype/chaos_game_short.py`).
8. How many people until two share a birthday? → 23 for 50%, 70 for 99.9%.
9. Multiply by 2 around a circle → cardioid; ×3 gives the light curve in a coffee cup.
10. Why do traffic jams appear from nothing? → a phantom jam wave.

**Avoid:** folds to the Moon, clacks/π, balls-and-mirrors remakes, ball-in-ring escapes, and primes as notes (3.8K for Play Paloooozaaaa).

**Before producing any idea:** search the topic over the last 30 days. If three or more Shorts already use it, change the twist or skip it.
