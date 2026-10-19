# CLAUDE.md

## Project

Football Game Simulator: a command-line tool that simulates an American football game play by play and prints the final score, team stats and player stats (or win odds over many games with `--sims`). Personal tool for TCSS 490 Artifact 2. I am the only user.

## Goal and scope

- Do one real thing well: simulate a game and report score and stats. Keep it small; this is a first build.
- Do not add features I did not ask for. If an idea would expand scope, ask first.
- Out of scope for now: penalties, timeouts, two-point conversions, individual defenders, real team or player data, a web UI.

## Stack

- Language/runtime: Python 3, standard library only
- Dependencies: none. Keep it that way.
- Run: `python3 footballsim.py TAC RNR` (see README for flags)
- Test/verify: `python3 -m unittest discover -s tests -v`

## How the code is organized

- `footballsim.py`: `Team` (validated data), `Game` (play-by-play engine; all randomness goes through `self.rng`, so a seed reproduces a game), reporting functions, and `main()`.
- `teams.json`: ratings 1-100, about 70 is average.
- Field position is `yl`, yards from the possessing team's own goal line (100 = end zone). Call `advance()` for the clock before possession changes.
- Tuning constants (play-call rates, yardage means, sack and interception rates) are inline in the play methods. If you change one, rerun the realism tests; they check NFL-like averages.

## Working agreements

- Commit after each working step with a short, descriptive message so I can roll back.
- Before changing existing behavior, say what you plan to change.
- After building something, run it and show me the real output rather than saying it works.
- Run the tests before every commit. A failing realism test means the tuning drifted, not that the test is wrong.
- Append an entry to `BUILD_LOG.md` at the end of each session: what was planned, what changed, what broke.
- Never commit secrets or API keys. Use environment variables and keep `.env` in `.gitignore`.

## Current state

Working. Single game, play-by-play, `--sims`, team validation and 21 passing tests. Averages over 600 games sit near 19 points, 338 yards and 5.4 yards per play per team. Next ideas: team stat leaders in `--sims`, penalties, a season mode.
