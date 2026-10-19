# NFL Game Simulator

> TCSS 490 — Artifact 2: Something You Will Use

A simulator that plays an NFL game between any two of the 32 teams, play by play, and shows the final score, team stats and player stats. Run it a thousand times to see each team's win odds. It works as a command-line tool and as a web page. Built for me, for settling arguments and for fun.

## What it does

- Simulates a full game: four quarters, downs and field position, runs, passes, sacks, interceptions, fumbles, punts, field goals, extra points, a two-minute drill, and sudden-death overtime for ties.
- Prints the **final score** with a line score by quarter, **team stats** (yards, plays, first downs, turnovers, sacks) and **player stats** (passing, rushing, receiving, kicking) for the real starters.
- `--sims N` runs N games and shows win percentage, average points, average yards and the most common final scores.
- All 32 teams are in `nfl_teams.json`, with ratings built from 2026 season stats (see below).

Not modeled: penalties, timeouts, two-point conversions, individual defenders, injuries, and the modern overtime rules.

## Run it

Needs Python 3 and nothing else (no dependencies).

```bash
python3 footballsim.py --list                       # show all 32 teams and their codes
python3 footballsim.py SEA KC                       # one game
python3 footballsim.py SEA KC --seed 42             # repeatable game
python3 footballsim.py SEA KC --play-by-play        # every play
python3 footballsim.py SEA KC --sims 1000           # win odds and averages
python3 footballsim.py                              # a random matchup
```

Sample (`python3 footballsim.py SEA KC --seed 4`):

```
FINAL: Seattle Seahawks 24, Kansas City Chiefs 17
```

## Use it in a browser

The web page (`index.html`) runs the same Python engine inside your browser using [Pyodide](https://pyodide.org), so there is only one copy of the game logic. Pick two teams, press **Play one game** or **Play 1,000 games**, and read the scoreboard, team stats and player stats. **Options** has a seed and a play-by-play switch. The page address remembers the game (`?a=SEA&b=KC&seed=4`), so you can send someone a link to replay it.

To try it on your computer, serve the folder (opening `index.html` directly will not work, because browsers block it from loading the data files):

```bash
python3 -m http.server 8000
# then open http://localhost:8000
```

It needs an internet connection for Pyodide (version 0.28.3, about 10 MB, downloaded the first time) and the fonts.

To put it online for free, the repo includes a GitHub Actions workflow (`.github/workflows/deploy.yml`). On every push to `main` it runs the tests, and if they pass it publishes the web files to GitHub Pages. One-time setup: in the repo, open **Settings, Pages**, and under **Build and deployment** set **Source** to **GitHub Actions** (the workflow also tries to turn this on by itself). Watch the run in the **Actions** tab. The site appears at `https://<your-username>.github.io/<repo-name>/` once it finishes. Only the web files are published, not the tests or tools.

## Where the data comes from

- **Starters:** QB, two RBs, three WRs, a TE and the kicker for each team, from the fantasynerds.com depth chart pages, checked against Ourlads. I corrected Atlanta's QB to Michael Penix Jr. after the two sources disagreed. Captured October 18, 2026.
- **Team ratings:** pass blocking, run blocking, pass rush, pass defense and run defense come from 2026 NFL.com team stats (about five games in). Each stat is compared with the other 31 teams, and 70 is average.
- **Player ratings are unofficial estimates.** They are my own judgment for well-known players plus a small nudge from the team's efficiency. They are not from any official rating. Edit them in `tools/build_nfl_teams.py` and rerun it, or edit `nfl_teams.json` directly.
- Rosters change weekly and the stats are a five-game sample, so treat the results as entertainment.

`teams.json` still holds three fictional teams (use `--teams-file teams.json`).

## Verify it works

```bash
python3 -m unittest discover -s tests -v
```

40 tests cover:

- **Repeatability:** the same seed gives the same game, line for line.
- **Stats add up** over 150 random games: points equal 6 per touchdown plus extra points plus 3 per field goal, quarter scores sum to the final score, receiving yards equal passing yards, and team yards equal rushing plus net passing.
- **Realism** over 400 games: points per team, plays, yards per play, turnovers, completion %, yards per carry, pass/run mix and field goal % all land in NFL-like ranges. A second check does the same across random NFL matchups.
- **NFL data:** all 32 teams are present, ratings are centered on 70, no duplicate player names within a team, and every team can play a game.
- **Ratings matter:** a team boosted by 15 rating points wins well over 62% of games.
- **Bad input and the command line:** unknown teams, the same team twice, lowercase codes, random matchups, `--sims` and `--list`.
- **The data the web page uses:** the JSON for one game and for 1,000 games matches the engine, player lines add up, and bad input gives plain error messages.

Not covered by these tests: how the page looks and loading Pyodide from the internet. Open the deployed page in a browser after each deploy to check those.

## Project files

| File | Purpose |
| --- | --- |
| `footballsim.py` | The simulator, command-line interface and the JSON functions the web page uses |
| `index.html`, `style.css` | The web page and its styling |
| `app.js` | Web page logic: team pickers, buttons, drawing the results |
| `worker.js` | Loads Pyodide and runs `footballsim.py` off the main thread |
| `.nojekyll` | Tells GitHub Pages to serve the files as they are |
| `.github/workflows/deploy.yml` | Runs the tests, then publishes the web page to GitHub Pages |
| `nfl_teams.json` | All 32 NFL teams, rosters and ratings (generated) |
| `tools/build_nfl_teams.py` | Raw rosters and stats plus the code that turns them into ratings |
| `teams.json` | Three fictional teams for testing |
| `tests/test_footballsim.py` | Unit, data and realism tests |
| `CLAUDE.md` | Standing instructions Claude Code loads each session |
| `BUILD_LOG.md` | What I planned and what changed, in order |

## Status

Built with Claude Code for TCSS 490, Autumn 2026. See `BUILD_LOG.md` for the history.
