# CLAUDE.md

## Project

NFL Game Simulator: simulates a game between any two NFL teams play by play and shows the final score, team stats and player stats (or win odds over many games). It runs as a command-line tool (`footballsim.py`) and as a web page (`index.html`) that runs the same Python in the browser with Pyodide. Personal tool for TCSS 490 Artifact 2. I am the only user.

## Goal and scope

- Do one real thing well: simulate a game and report score and stats. Keep it small; this is a first build.
- Do not add features I did not ask for. If an idea would expand scope, ask first.
- Out of scope for now: penalties, timeouts, two-point conversions, individual defenders, injuries, a web UI.

## Stack

- Language/runtime: Python 3, standard library only
- Dependencies: none. Keep it that way.
- Run: `python3 footballsim.py SEA KC` (see README for flags)
- Test/verify: `python3 -m unittest discover -s tests -v`

## How the code is organized

- `footballsim.py`: `Team` (validated data), `Game` (play-by-play engine; all randomness goes through `self.rng`, so a seed reproduces a game), reporting functions, and `main()`.
- `nfl_teams.json`: generated. Do not hand-edit if you can avoid it; change `tools/build_nfl_teams.py` and rerun it.
- `tools/build_nfl_teams.py`: holds the raw roster and stat tables (captured Oct 18, 2026) and turns them into ratings (z-score vs the league, 70 is average). Player ratings are my unofficial estimates, listed in `OVERRIDES`.
- `teams.json`: three fictional teams, used by some tests.
- Web page: `index.html` + `style.css` + `app.js` (UI) and `worker.js` (loads Pyodide from the jsDelivr npm CDN, pinned to one version, writes `footballsim.py` and `nfl_teams.json` into Pyodide's file system, and calls `footballsim.run_for_web`). The page never re-implements game logic. If you change what the engine returns, change `game_to_dict`/`sims_to_dict` and `app.js` together, and keep `run_for_web` returning JSON.
- Do not use `.score` for anything but the scoreboard numerals in `style.css`; play-by-play highlights use `.scoring`.
- To try the page locally: `python3 -m http.server 8000` and open http://localhost:8000 (opening the file directly fails). Page layout and the CDN load are not covered by the unit tests; look at it in a browser after changes.
- Field position is `yl`, yards from the possessing team's own goal line (100 = end zone). Call `advance()` for the clock before possession changes.
- Tuning constants (play-call rates, yardage means, sack and interception rates) are inline in the play methods. If you change one, rerun the realism tests; they check NFL-like averages.

## Working agreements

- Commit after each working step with a short, descriptive message so I can roll back.
- Before changing existing behavior, say what you plan to change.
- After building something, run it and show me the real output rather than saying it works.
- Run the tests before every commit. A failing realism test means the tuning drifted, not that the test is wrong.
- Rosters and stats go stale. When refreshing data, re-fetch from the sources named in the build script, say which were used, and never present estimated ratings as official.
- Append an entry to `BUILD_LOG.md` at the end of each session: what was planned, what changed, what broke.
- Never commit secrets or API keys. Use environment variables and keep `.env` in `.gitignore`.

## Current state

Working. All 32 NFL teams, single game, play-by-play, `--sims`, random matchup, a web page, and 40 passing tests. Averages over 1000 random NFL matchups: about 19 points, 338 yards and 5.4 yards per play per team. The web page's logic was checked end to end with a throwaway script (jsdom plus Pyodide in Node), but I have not seen it in a real browser, and the Pyodide CDN load is unverified. Next ideas: look at the page in a browser and fix layout problems, publish with GitHub Pages, refresh the data each week, stat leaders in `--sims`, penalties, a season mode.
