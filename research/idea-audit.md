# Idea audit (8 Nov 2026)

22 new pitches went through two independent reviewers before anything was built.

## 1. Blind judge, tested against hidden real Shorts

The judge was a separate agent with no web access. It got:
- the answer key: every real Short in the niche with known views;
- 32 pitches, all in the same card format: 22 new ideas, plus 10 real existing Shorts with their views removed.

It wasn't told that some pitches were real. Scoring it on those 10 shows how far to trust its ratings of the new ideas.

| Hidden real Short | Actual views | Judge's tier | P(1M+) | Judge's verdict |
|---|---:|---|---:|---|
| How Many Cuts To Reach An Atom? | 5.03M | C | 5% | KILL |
| Can You Get Infinite Chocolate? | 2.57M | B | 9% | KILL |
| This Is the Fastest Way to Board a Plane | 1.21M | B | 16% | BUILD (#2 pick) |
| Growing a Hole Until It Can Eat the Earth | 1.13M | C | 4% | KILL |
| Will The DVD Logo Ever Hit The Corner? | 600K | B | 22% | BUILD (#1 pick) |
| How Many Balloons To Lift A House? | 267K | B | 10% | REWORK |
| What If One Cell Kept Doubling? | 119K | B | 7% | REWORK |
| 512 Balls, One Dot. Why Do They All Meet? | 86K | C | 3% | KILL |
| How Heavy Is A Cloud? | 24K | C | 5% | KILL |
| I Gave Every Prime Number Its Own Note | 3.8K | C | 2% | KILL |

**Result:**
- The judge got the tier right for all 6 non-hits.
- It rated none of the 4 real hits as 1M+.
- It would have killed 3 of the 4 hits.
- Its top pick was a real Short with 600K views.
- Its P(1M+) averages 8.5% for hits and 8.2% for non-hits, so it can't tell them apart (AUC ≈ 0.56).

The rule that misled it most was "remakes of folding die". That rule killed "Cuts To Reach An Atom", a twist on folding that got 5.0M.

**Use:** treat the judge as a filter for obvious misses, not as a hit predictor.

## 2. Market and fact check

A second agent searched YouTube (Shorts filter, sorted by relevance, popularity and "this month") for each new idea, counted recent uploads on the topic, and verified every number in each payoff.

| Status | Ideas |
|---|---|
| Open (proven demand, few recent copies) | 12-fold paper (Gallivan angle), tautochrone, Buffon's needle, chaos game |
| Open, demand unproven | Rumor doubling |
| Crowded | Tower of Hanoi, Langton's ant, Collatz, chessboard grains, traffic jams, ancestors, light speed, biggest star, Galton board |
| Saturated (exact titles already exist; most get 1K–5K) | Missing square, billion seconds, birthday paradox, Sun as basketball, heartbeats, times-table circle, 52! shuffles, Monty Hall |

Fact fixes it found:
- **Chessboard:** the last square holds 2⁶³ grains. 2⁶⁴ − 1 is the whole board. The harvest comparison is 650–1,500 years, depending on grain mass.
- **Biggest star:** UY Scuti has been revised down to 909 R☉, which is about 750 million Suns. Stephenson 2-18 is now about 6 billion Suns, and that figure is uncertain.
- **Coffee-cup curve:** the light curve in a coffee cup is a nephroid only under distant light, such as sunlight.
- **Collatz:** now verified up to 2⁷¹ ≈ 2.4×10²¹.
- **Heartbeats:** 2.5–3 billion is safer than "3 billion".
- **Rumor:** "tells two" triples the count each step; "doubles" is the correct mechanic.

## 3. Decision: build the 12-fold paper Short

It's the only idea that clears all four tests:

1. **Strongest hit family.** Six folding or cutting Shorts reached 1M+ in five weeks. Older Shorts on the topic have 88.9M ("Can you fold paper more than 7 times?") and 28.6M ("Folding A Paper To The Moon").
2. **Open on its exact angle.** About 5 Shorts cover the Gallivan / 12-fold angle, all under 10K.
3. **Facts verified.** Gallivan folded paper 12 times in January 2002, using about 1.2 km of toilet paper. The formula L = πt/6·(2ⁿ+4)(2ⁿ−1) is correct.
4. **A twist, not a copy.** That's the pattern the hidden-Short test showed works ("Cuts", 5.0M). Straight copies ("Fold Paper 42 Times and It Reaches the MOON", 13.7K) don't.

Running the formula for office paper (0.1 mm) gives better beats than the brief had:

| Folds | Strip length needed | Comparison |
|---:|---|---|
| 6 | 22 cm | Fits on a sheet of A4 |
| 7 | 88 cm | A4 runs out: the familiar 7-fold limit |
| 10 | 55 m | Just under the Tower of Pisa (57 m) |
| 12 | 879 m | Taller than the Burj Khalifa (828 m) |
| 42 (the famous "to the Moon") | 1.01×10²¹ m ≈ 107,000 light-years | About the width of the Milky Way |

## Runners-up

- **Chaos game:** open, and the sonified version has 3.75M. Already rendered (`prototype/chaos_game_short.py`).
- **Tautochrone:** open, and its sibling, the brachistochrone Short, has 101.7M. Needs a new title, not the "Why do they all land together?" pattern.
- **Phantom traffic jam:** crowded, but the topic is trending right now: an 11.2M Short under a month old.
