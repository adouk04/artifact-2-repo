# Football Game Simulator

> TCSS 490 — Artifact 2: Something You Will Use

A command-line simulator that plays an American football game play by play and prints the final score, team stats and player stats. Run it a thousand times to see each team's win odds. Built for me, for settling arguments and for fun.

## What it does

- Simulates a full game: four quarters, downs and field position, runs, passes, sacks, interceptions, fumbles, punts, field goals, extra points, a two-minute drill, and sudden-death overtime for ties.
- Prints the **final score** with a line score by quarter, **team stats** (yards, plays, first downs, turnovers, sacks) and **player stats** (passing, rushing, receiving, kicking).
- `--sims N` runs N games and shows win percentage, average points, average yards and the most common final scores.
- Teams and player ratings live in `teams.json` (three fictional teams included). Edit the numbers to build your own matchups.

Not modeled: penalties, timeouts, two-point conversions, individual defenders, and the modern overtime rules.

## Run it

Needs Python 3 and nothing else (no dependencies).

```bash
python3 footballsim.py --list                       # show teams
python3 footballsim.py TAC RNR                      # one game
python3 footballsim.py TAC RNR --seed 42            # repeatable game
python3 footballsim.py TAC RNR --play-by-play       # every play
python3 footballsim.py TAC RNR --sims 1000          # win odds and averages
```

Sample output (seed 11):

```
FINAL: Tacoma Tides 24, Rainier Rockets 30 (OT)
```

## Make your own team

Add an entry to `teams.json`. Ratings are whole numbers from 1 to 100 (about 70 is average):

- Team: `pass_block`, `run_block`, `pass_rush`, `pass_defense`, `run_defense`
- Players: one `qb`, a list of `rbs`, a list of `receivers` (each with `pos` of `WR` or `TE`) and a `kicker`

Bad data (a rating of 150, a missing kicker) is rejected with a clear error.

## Verify it works

```bash
python3 -m unittest discover -s tests -v
```

21 tests cover:

- **Repeatability:** the same seed gives the same game, line for line.
- **Stats add up** over 150 random games: points equal 6 per touchdown plus extra points plus 3 per field goal, quarter scores sum to the final score, receiving yards equal passing yards, and team yards equal rushing plus net passing.
- **Realism** over 400 games: points per team, plays, yards per play, turnovers, completion %, yards per carry, pass/run mix and field goal % all land in NFL-like ranges.
- **Ratings matter:** a team boosted by 15 rating points wins well over 62% of games.
- **Bad input and CLI errors** are handled.

## Project files

| File | Purpose |
| --- | --- |
| `footballsim.py` | The simulator and command-line interface |
| `teams.json` | Teams, ratings and rosters (edit me) |
| `tests/test_footballsim.py` | Unit and realism tests |
| `CLAUDE.md` | Standing instructions Claude Code loads each session |
| `BUILD_LOG.md` | What I planned and what changed, in order |

## Status

Built with Claude Code for TCSS 490, Autumn 2026. See `BUILD_LOG.md` for the history.
