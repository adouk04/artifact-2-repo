# Build Log

A running record of what I planned and what changed. Newest entries at the bottom.

## Entry 1 — Plan

- **Date:** 2026-10-18 (due tonight, 11:59 PM)
- **Idea:** Football game simulator: pick two teams and see the final score and player stats.
- **Why I'll actually use it:** I like football and want to see how matchups could play out, and I can keep adding to it (real teams, seasons) as the quarter goes on.
- **Scope (one real thing):** Simulate one game play by play, print score, team stats and player stats. Optional `--sims N` for win odds.
- **Out of scope:** Penalties, timeouts, two-point conversions, individual defenders, real NFL data, a web UI.
- **Plan:**
  1. Set up repo, `CLAUDE.md`, and this log
  2. Build the smallest version that runs (Python, no dependencies, fictional teams in JSON)
  3. Test it, and check that the averages look like real football
  4. Fill in the portfolio card

## Entry 2 — Built the simulator and checked it

- **Planned:** A drive-and-play engine with downs, field position, a clock, scoring and stats, plus tests.
- **Changed:**
  - `footballsim.py`: `Team` validation, `Game` engine (runs, passes, sacks, interceptions, fumbles, punts, field goals, extra points, halftime, hurry-up clock, sudden-death overtime), report printing, `--sims`, `--seed`, `--play-by-play`, `--list`.
  - `teams.json`: three fictional teams (TAC, RNR, OLY).
  - `tests/test_footballsim.py`: 21 tests.
- **What broke / what I fixed:**
  - First version ran about 70% passes (long-yardage situations stacked on a 57% base), so only about 20 rushes a game. I lowered the base pass rate to 50% and the long-yardage bump to +12 points. Now about 34 pass attempts and 27 rushes per team.
  - Scoring was low (about 18 points per team). I raised average pass yardage and the interception rate slightly. Now about 19 points, 338 yards, 5.4 yards per play, 6.8 yards per pass attempt, 4.5 per carry, 65.6% completions, 1.2 turnovers (600 games, TAC vs RNR). That is slightly under real NFL scoring, so I kept the test range wide (16 to 26).
  - Piping output into `head` raised a `BrokenPipeError`. Fixed by catching it at the entry point.
- **How I checked it:**
  - Ran single games, read the play-by-play, and checked down and distance and field position carry over correctly between plays.
  - Found an overtime game (seed 11) and read its last plays.
  - `python3 -m unittest discover -s tests`: 21 tests pass. They check that points equal touchdowns, extra points and field goals, quarter scores sum to the final, receiving yards equal passing yards, the same seed gives the same game, a boosted team wins over 62% of games, and the realism ranges hold.
- **Next:** Fill in the portfolio card, push the repo. Later: stat leaders in `--sims`, penalties, a season mode.

## Entry 3 — Plan change: real NFL teams

- **Planned:** I changed the plan from fictional teams to all 32 NFL teams with real starters. "Real NFL data" is now in scope; the other out-of-scope items stand.
- **Changed:**
  - `nfl_teams.json` (generated) and `tools/build_nfl_teams.py`, which holds the raw roster and stat tables and the rating formulas, so the ratings can be reproduced.
  - `footballsim.py` now defaults to the NFL file. With no teams given it picks a random matchup. `teams.json` is still available with `--teams-file`.
  - Tests went from 21 to 33: NFL file has 32 teams, ratings centered on 70, no duplicate names, every team can play, league-wide realism holds, and more command-line cases.
- **Where the data came from:**
  - Starters from fantasynerds.com depth chart pages (one fetch per team), checked against Ourlads.
  - Team stats from NFL.com 2026 regular-season pages: offense and defense, passing and rushing, captured October 18, 2026.
  - Team ratings are z-scores against the league (70 + 6 per standard deviation). Player ratings are my own unofficial estimates for well-known players, with a small nudge from team efficiency.
- **What broke / what I found:**
  - Ourlads loaded only 4 of 32 teams, so it could not be the main source.
  - Jacksonville's page returned nothing at first because I used the wrong URL code (`JAX`); `JAC` worked.
  - Atlanta's QB differed between sources (Tua Tagovailoa vs Michael Penix Jr.). I checked a September 21, 2026 report and the Ourlads chart from October 17, which both say Penix, and used him.
  - NFL.com's sack page did not match its passing pages for some teams, so I ignored it and used sacks taken and made from the passing pages.
  - NFL.com does not show games played, so the ratings use rates (yards per attempt, sack rate) rather than totals.
- **Limits I know about:** the stats are about five games, rosters change weekly, a few numbers were read off summarized web pages and I did not independently re-check each one, and the player ratings are opinion. The README says so.
- **How I checked it:**
  - Ran `SEA KC`: one game, then 1000 simulated games. Kansas City won 58.5%, which fits its strong defensive numbers.
  - Checked that the ratings average 70 (range about 56 to 84) and that Josh Allen, Lamar Jackson and Patrick Mahomes come out as the top three quarterbacks.
  - Across 1000 random NFL matchups: about 19 points, 338 yards, 5.4 yards per play, 64% completions and 1.3 turnovers per team. All 33 tests pass.
- **Next:** Push the repo, fill in the portfolio card. Later: refresh the data weekly and add stat leaders to `--sims`.

## Entry 4 — Added a web page

- **Planned:** A web UI so I can pick teams and see results in a browser, and so Artifact 2 has something to link to.
- **Decision:** Reuse the Python engine in the browser with Pyodide instead of rewriting it in JavaScript. One copy of the game logic means the 40 tests cover what the page runs. The cost is a first-load download of about 10 MB.
- **Changed:**
  - `footballsim.py`: `player_lines`, `game_to_dict`, `sims_to_dict` and `run_for_web` return plain JSON-ready data. The command-line output now builds from the same functions and is unchanged (seed 4, SEA vs KC is still 24-17).
  - New `index.html`, `style.css`, `app.js` and `worker.js`; `.nojekyll` for GitHub Pages.
  - 7 new tests for the JSON data (33 to 40 total).
  - Design: turf green and chalk, with the yellow first-down line as the one accent. After a game the line sweeps to the winner's side of the scoreboard. In the 1,000-game view the line marks an even split. Type is Big Shoulders Display for scores and team names, Atkinson Hyperlegible for everything else.
  - The page address remembers the game (`?a=SEA&b=KC&seed=4`), so a link replays it.
- **What broke / what I fixed:**
  - Passing a missing seed from JavaScript reached Python as a `JsNull` object and crashed. The Python wrapper now takes the seed as text and returns errors as JSON.
  - I used the CSS class `score` for both the scoreboard numerals and the highlighted scoring plays, so scoring plays would have rendered at 12rem. Renamed the play highlight to `scoring`.
  - `.visually-hidden` was used but not defined. Added it.
- **How I checked it:**
  - Ran `footballsim.py` inside Pyodide under Node: identical results to native Python (SEA 24-17 at seed 4, 40.0% vs 58.5% over 1,000 games). 1,000 games take about 1.7 seconds.
  - Loaded the real `index.html` and `app.js` in jsdom with a stand-in worker backed by that same Pyodide. Checked: 32 teams listed, the 24-17 scoreboard, line score, 8 stat rows, player tables, 142-play log, the 1,000-game view, both error messages, 50 random matchups, and a shared link that plays automatically. This script is not in the repo because it needs extra packages.
- **Not checked:** I have not seen the page in a real browser, so the layout and look are unreviewed, and I could not confirm that the jsDelivr link for Pyodide 314.0.7 loads (the files come from the npm package I tested with). Do both before relying on it.
- **Next:** Open it in a browser, fix whatever looks wrong, turn on GitHub Pages, and put the live link on the portfolio card.

## Entry 5 — Deploy with GitHub Actions

- **Planned:** Host the web page the same way as my portfolio, with a GitHub Actions workflow.
- **Changed:** Added `.github/workflows/deploy.yml`. I read my portfolio repo's workflow and kept its triggers, permissions, concurrency group and action versions (`checkout@v4`, `configure-pages@v5` with `enablement: true`, `upload-pages-artifact@v3`, `deploy-pages@v4`). Two differences: a `test` job runs the unit tests first and the deploy waits for it, and only the seven web files are published (not tests or tools), so the site is smaller and cleaner.
- **How I checked it:** Parsed the YAML (two jobs, `deploy` needs `test`, triggers are push to main and manual run) and copied exactly the files the workflow publishes into a subfolder to confirm the page only needs those files and uses relative paths, so it works under `/<repo-name>/`.
- **Not checked:** I cannot run GitHub Actions from here, so the workflow has not run. The first push is the real test. If it fails at "Configure Pages", set Settings, Pages, Source to GitHub Actions by hand and re-run it.
- **Next:** Push, watch the Actions tab, open the live link, and put it on the portfolio card.

## Entry 6 — Fixed the page not starting on the live site

- **What happened:** The deployed page showed "The simulator could not start" and no games would run.
- **How I found the cause:** I opened the live site in a real browser and read the console: `importScripts` failed on `https://cdn.jsdelivr.net/npm/pyodide@314.0.7/pyodide.js`. The same URL downloaded fine with `fetch`, and the file parsed, but a worker would not load it. Testing other copies in a worker: Pyodide 0.27.7 and 0.28.3 from jsDelivr's official path, 0.27.7 from unpkg and 0.23.4 from cdnjs all loaded. Only the 314.0.7 npm copy failed. I don't know why; it's the newest version and I had only tested it in Node.
- **Changed:**
  - `worker.js`: now loads Pyodide 0.28.3 from `https://cdn.jsdelivr.net/pyodide/v0.28.3/full/`, and the download is inside the error handling, so a failure shows a real message instead of a generic one.
  - `app.js`: the "could not start" message now includes the browser's error text.
- **How I checked it:** In a real browser, I ran the new `worker.js` code against the live `footballsim.py` and `nfl_teams.json`: it loaded Python, then SEA vs KC at seed 4 gave Seattle 24, matching the command line. Unit tests still pass (40).
- **Lesson:** My earlier Node-only test could not catch a browser loading problem. I wrote "not checked" for exactly this in Entry 4; it was the thing that broke. Open the deployed page after every deploy.
- **Next:** Push, reload the live page, and play a game. Then fill in the portfolio card.

