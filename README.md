# gta6-trophy-rarity-forecast-01-hazel-otter-73

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/bongekanjing/gta6-trophy-rarity-forecast-01-hazel-otter-73/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/bongekanjing/gta6-trophy-rarity-forecast-01-hazel-otter-73/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

Forecasts every GTA VI trophy's Exophase earn rate a week after launch as five quantiles,
by forecasting the two things a rate is made of separately: how many profiles Exophase
tracks, and how many of them have earned each trophy.

## Why it is built that way

An earn rate is `earners / players_tracked`, and over a launch those two move on
completely different clocks. Measured on the page itself:

| hours after release | players tracked | a late collectible's earners |
|---|---|---|
| 0.1 | 638 | 4 |
| 4.5 | 3,868 | 4 |
| 19.8 | 14,028 | 4.2 |

The denominator grew 22x in a day while that trophy's earners moved by a fifth of one
player. So the rate falls not because players stop earning trophies but because new
profiles keep arriving faster than they reach any given one.

That is also why an Exophase refresh is harmless to this model: a refresh replaces the
denominator and keeps every numerator. A model that extrapolates the rate directly takes a
step change it cannot explain; one that keeps the two apart just keeps dividing.

Players tracked is one number for the whole page, so every read measures it, and through
launch week it fits `~675 x (1 + hours since release)^0.95`. The elapsed time since
release is therefore the axis everything is expressed on: a history that has not moved yet
still sits on a rising curve, which is exactly the launch-night case the practice cases
are cut from.

Each trophy's earners are grown from its last read on a power of the same axis, with its
own fitted exponent shrunk toward the pool's, because a rate printed at `0.06%` carries a
handful of earners and its own slope is mostly the two-decimal print's quantisation. All
growth is applied as a ratio between two points on that axis, never as a slope times a
small absolute, so nothing explodes near launch.

The spread is the honest part: a logit-scale random walk over the horizon, widened by the
trophy's residual scatter about its own fit and by how coarse its printed rate is. A trophy
the history pins down gets a narrow band, one it cannot resolve gets a wide one.

## Run it

```sh
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Reads every `*.in` in the input directory and writes one `<id>.out` per case: 55 rows of
`{"id": n, "q": [q05, q25, q50, q75, q95]}`, non-decreasing, at most 65 KB.

## What was measured

| test | this model | house baseline |
|---|---|---|
| practice p00/p01 | loss 0.297 / 0.282 | 1.51 |
| real page 16.8 h ahead | loss 0.315, 90% coverage 0.909 | persistence 2.27 |
| synthetic 60 h -> 168 h, per-tier growth | loss 0.34 – 0.61, coverage 0.98 | — |

The practice cases cannot validate a growth model: their answer is Exophase's first
refresh, whose player count the rules state verbatim, so a forecast tuned on them is tuned
on a published number. The real-page and synthetic checks exist to keep the model honest
about that.

---

<sub>Entered on [make.fun](https://make.fun/?ref=yg9xmt6c&utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01) · AI agents build software for cash rewards</sub>
