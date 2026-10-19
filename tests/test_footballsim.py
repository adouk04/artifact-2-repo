"""Tests for footballsim. Run from the repo root:

    python3 -m unittest discover -s tests -v
"""

import contextlib
import copy
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import footballsim as fs  # noqa: E402

TEAMS = fs.load_teams(ROOT / "teams.json")


def play(seed, a="TAC", b="RNR"):
    return fs.Game(TEAMS[a], TEAMS[b], seed=seed).run()


class Determinism(unittest.TestCase):
    def test_same_seed_same_game(self):
        g1, g2 = play(123), play(123)
        self.assertEqual(g1.points, g2.points)
        self.assertEqual(g1.log, g2.log)

    def test_different_seeds_differ(self):
        results = {tuple(play(s).points.values()) for s in range(20)}
        self.assertGreater(len(results), 5)


class Consistency(unittest.TestCase):
    """Stats must add up, whatever the random seed."""

    def test_stats_add_up_over_many_games(self):
        for seed in range(150):
            g = play(seed)
            for ab in g.order:
                ps = list(g.pstats[ab].values())
                s = lambda key: sum(p[key] for p in ps)

                tds = s("rush_td") + s("pass_td")
                self.assertEqual(g.points[ab], 6 * tds + s("xp_made") + 3 * s("fg_made"), f"seed {seed}")
                self.assertEqual(sum(g.quarters[ab]), g.points[ab], f"seed {seed}")
                self.assertEqual(s("pass_td"), s("rec_td"), f"seed {seed}")
                self.assertEqual(s("pass_yds"), s("rec_yds"), f"seed {seed}")
                self.assertEqual(s("pass_comp"), s("rec"), f"seed {seed}")
                self.assertEqual(s("pass_att"), s("targets"), f"seed {seed}")
                self.assertLessEqual(s("pass_comp"), s("pass_att"))
                self.assertLessEqual(s("xp_made"), s("xp_att"))
                self.assertLessEqual(s("fg_made"), s("fg_att"))

                t = g.totals(ab)
                self.assertEqual(t["total_yds"], t["rush_yds"] + t["pass_yds"])

    def test_clock_never_runs_past_the_limit(self):
        for seed in range(100):
            g = play(seed)
            limit = fs.REGULATION + (fs.OVERTIME if g.ot else 0)
            self.assertLessEqual(g.elapsed, limit)
            self.assertGreaterEqual(g.elapsed, fs.REGULATION)

    def test_only_tied_games_go_to_overtime(self):
        for seed in range(100):
            g = play(seed)
            if g.ot:
                self.assertTrue(g.log and any("Overtime" in line for line in g.log))

    def test_player_names_come_from_the_roster(self):
        for seed in range(30):
            g = play(seed)
            for ab in g.order:
                t = g.teams[ab]
                roster = {t.qb["name"], t.kicker["name"]}
                roster |= {p["name"] for p in t.rbs} | {p["name"] for p in t.receivers}
                self.assertTrue(set(g.pstats[ab]) <= roster)


class Realism(unittest.TestCase):
    """Averages over many games should look like real football."""

    @classmethod
    def setUpClass(cls):
        games = [play(seed) for seed in range(400)]
        cls.n = len(games) * 2
        totals = {}

        def add(key, value):
            totals[key] = totals.get(key, 0) + value

        for g in games:
            for ab in g.order:
                ps = list(g.pstats[ab].values())
                t = g.totals(ab)
                add("points", g.points[ab])
                add("plays", t["plays"])
                add("yards", t["total_yds"])
                add("turnovers", t["turnovers"])
                for key in ("pass_att", "pass_comp", "pass_yds", "rush_att", "rush_yds", "fg_att", "fg_made"):
                    add(key, sum(p[key] for p in ps))
        cls.t = totals

    def test_points_per_team(self):
        self.assertTrue(16 <= self.t["points"] / self.n <= 26, self.t["points"] / self.n)

    def test_plays_per_team(self):
        self.assertTrue(55 <= self.t["plays"] / self.n <= 72, self.t["plays"] / self.n)

    def test_yards_per_play(self):
        self.assertTrue(4.6 <= self.t["yards"] / self.t["plays"] <= 6.2)

    def test_turnovers_per_team(self):
        self.assertTrue(0.8 <= self.t["turnovers"] / self.n <= 2.2, self.t["turnovers"] / self.n)

    def test_completion_percentage(self):
        self.assertTrue(0.58 <= self.t["pass_comp"] / self.t["pass_att"] <= 0.70)

    def test_yards_per_carry(self):
        self.assertTrue(3.8 <= self.t["rush_yds"] / self.t["rush_att"] <= 5.0)

    def test_pass_run_mix(self):
        share = self.t["pass_att"] / (self.t["pass_att"] + self.t["rush_att"])
        self.assertTrue(0.45 <= share <= 0.65, share)

    def test_field_goal_percentage(self):
        self.assertTrue(0.70 <= self.t["fg_made"] / self.t["fg_att"] <= 0.92)


class TeamStrength(unittest.TestCase):
    def test_much_stronger_team_usually_wins(self):
        data = json.loads((ROOT / "teams.json").read_text())["teams"]["RNR"]
        strong = copy.deepcopy(data)
        strong["name"] = "Strong"
        bump = lambda p: p.update(rating=min(100, p["rating"] + 15))
        for key in fs.RATING_KEYS:
            strong[key] = min(100, strong[key] + 15)
        bump(strong["players"]["qb"])
        bump(strong["players"]["kicker"])
        for p in strong["players"]["rbs"] + strong["players"]["receivers"]:
            bump(p)
        boosted = fs.Team("STR", strong)

        wins = sum(
            fs.Game(boosted, TEAMS["RNR"], seed=s).run().winner() == "STR" for s in range(300)
        )
        self.assertGreater(wins / 300, 0.62, wins / 300)


class Validation(unittest.TestCase):
    def good(self):
        return copy.deepcopy(json.loads((ROOT / "teams.json").read_text())["teams"]["TAC"])

    def test_rating_out_of_range(self):
        d = self.good()
        d["pass_block"] = 150
        with self.assertRaises(ValueError):
            fs.Team("BAD", d)

    def test_missing_field(self):
        d = self.good()
        del d["players"]["kicker"]
        with self.assertRaises(ValueError):
            fs.Team("BAD", d)

    def test_bad_receiver_position(self):
        d = self.good()
        d["players"]["receivers"][0]["pos"] = "QB"
        with self.assertRaises(ValueError):
            fs.Team("BAD", d)


def run_cli(*args):
    """Run main() with output captured; return (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = fs.main(list(args))
    return code, out.getvalue(), err.getvalue()


class NflData(unittest.TestCase):
    """The real-team file: all 32 teams, sane ratings, and still realistic."""

    @classmethod
    def setUpClass(cls):
        cls.teams = fs.load_teams(ROOT / "nfl_teams.json")

    def test_has_all_32_teams(self):
        self.assertEqual(len(self.teams), 32)
        self.assertEqual(len({t.name for t in self.teams.values()}), 32)

    def test_ratings_are_centered_on_average(self):
        for key in fs.RATING_KEYS:
            mean = sum(getattr(t, key) for t in self.teams.values()) / 32
            self.assertTrue(68 <= mean <= 72, f"{key} mean {mean}")

    def test_no_duplicate_player_names_within_a_team(self):
        for t in self.teams.values():
            names = [t.qb["name"], t.kicker["name"]] + [p["name"] for p in t.rbs + t.receivers]
            self.assertEqual(len(names), len(set(names)), t.name)

    def test_every_team_can_play_and_stats_add_up(self):
        abbrs = list(self.teams)
        for i, a in enumerate(abbrs):
            b = abbrs[(i + 1) % len(abbrs)]
            g = fs.Game(self.teams[a], self.teams[b], seed=i).run()
            for ab in g.order:
                self.assertEqual(sum(g.quarters[ab]), g.points[ab], f"{a} vs {b}")

    def test_league_wide_averages_stay_realistic(self):
        import random

        pick = random.Random(0)
        games = []
        for seed in range(300):
            a, b = pick.sample(list(self.teams), 2)
            games.append(fs.Game(self.teams[a], self.teams[b], seed=seed).run())
        n = len(games) * 2
        points = sum(sum(g.points.values()) for g in games) / n
        turnovers = sum(g.totals(ab)["turnovers"] for g in games for ab in g.order) / n
        self.assertTrue(16 <= points <= 26, points)
        self.assertTrue(0.8 <= turnovers <= 2.2, turnovers)

    def test_best_quarterback_team_beats_worst_more_often_than_not(self):
        wins = sum(
            fs.Game(self.teams["BUF"], self.teams["ARI"], seed=s).run().winner() == "BUF" for s in range(200)
        )
        self.assertGreater(wins / 200, 0.5, wins / 200)


class Fantasy(unittest.TestCase):
    """Fantasy points (PPR) are computed from the same stats the tables show."""

    def test_scoring_by_hand(self):
        # 281 pass yds (11.24) + 1 TD (4) - 1 INT (2) = 13.24
        self.assertEqual(fs.fantasy_points({"pass_yds": 281, "pass_td": 1, "interceptions": 1}), 13.2)
        # 47 rush yds (4.7) + 2 rush TD (12) + 5 catches (5) + 82 rec yds (8.2) = 29.9
        self.assertEqual(fs.fantasy_points({"rush_yds": 47, "rush_td": 2, "rec": 5, "rec_yds": 82}), 29.9)
        # a lost fumble costs 2; 2 extra points and a 54-yard field goal (5) = 7
        self.assertEqual(fs.fantasy_points({"fumbles": 1}), -2.0)
        self.assertEqual(fs.fantasy_points({"xp_made": 2, "fg_fantasy": 5}), 7.0)
        self.assertEqual(fs.fantasy_points({}), 0.0)

    def test_game_fantasy_matches_the_stat_lines(self):
        teams = fs.load_teams(ROOT / "nfl_teams.json")
        for seed in range(20):
            g = fs.Game(teams["SEA"], teams["KC"], seed=seed).run()
            for abbr in g.order:
                lines = fs.player_lines(g, abbr)
                by_name = {p["name"]: p["pts"] for p in lines["fantasy"]}
                self.assertEqual(list(by_name.values()), sorted(by_name.values(), reverse=True))
                total = sum(by_name.values())
                base = sum(p["yds"] * 0.04 + p["td"] * 4 - p["int"] * 2 for p in lines["passing"])
                base += sum(p["yds"] * 0.1 + p["td"] * 6 - p["fum"] * 2 for p in lines["rushing"])
                base += sum(p["rec"] + p["yds"] * 0.1 + p["td"] * 6 for p in lines["receiving"])
                k = lines["kicking"][0] if lines["kicking"] else {"xp_made": 0, "fg_made": 0}
                low = base + k["xp_made"] + 3 * k["fg_made"]
                high = base + k["xp_made"] + 5 * k["fg_made"]
                # each player's points are rounded to 0.1, so allow a little slack
                self.assertGreaterEqual(total, low - 0.8)
                self.assertLessEqual(total, high + 0.8)
                self.assertTrue(all(isinstance(v, float) for v in by_name.values()))

    def test_kicker_points_use_distance(self):
        teams = fs.load_teams(ROOT / "nfl_teams.json")
        for seed in range(40):
            g = fs.Game(teams["SEA"], teams["KC"], seed=seed).run()
            for abbr in g.order:
                for st in g.pstats[abbr].values():
                    if st.get("fg_made"):
                        self.assertGreaterEqual(st["fg_fantasy"], 3 * st["fg_made"])
                        self.assertLessEqual(st["fg_fantasy"], 5 * st["fg_made"])

    def test_sims_have_average_fantasy_points(self):
        teams = fs.load_teams(ROOT / "nfl_teams.json")
        d = json.loads(fs.run_for_web(teams, "SEA", "KC", seed=1, sims=30))
        for t in d["teams"]:
            self.assertTrue(t["avg_fantasy"])
            pts = [p["pts"] for p in t["avg_fantasy"]]
            self.assertEqual(pts, sorted(pts, reverse=True))
            self.assertTrue(all(p > 0 for p in pts))
            # the QB and the top receiver should average real fantasy production
            self.assertGreater(pts[0], 8)


class WebApi(unittest.TestCase):
    """run_for_web() is what the web page calls; it must return clean JSON."""

    @classmethod
    def setUpClass(cls):
        cls.teams = fs.load_teams(ROOT / "nfl_teams.json")

    def game(self, **kw):
        return json.loads(fs.run_for_web(self.teams, "SEA", "KC", seed=4, **kw))

    def test_game_matches_the_engine(self):
        d = self.game()
        g = fs.Game(self.teams["SEA"], self.teams["KC"], seed=4).run()
        self.assertEqual(d["kind"], "game")
        self.assertEqual({t["abbr"]: t["points"] for t in d["teams"]}, g.points)
        self.assertEqual(d["winner"], g.winner())
        for t in d["teams"]:
            self.assertEqual(sum(t["quarters"]), t["points"])
            self.assertEqual(len(t["quarters"]), 5 if d["ot"] else 4)

    def test_player_lines_are_complete(self):
        d = self.game()
        for t in d["teams"]:
            self.assertEqual(set(t["players"]), {"passing", "rushing", "receiving", "kicking", "fantasy"})
            self.assertEqual(len(t["players"]["passing"]), 1)
            self.assertEqual(
                sum(p["yds"] for p in t["players"]["receiving"]), t["players"]["passing"][0]["yds"]
            )
            self.assertEqual(
                t["stats"]["total_yds"],
                sum(p["yds"] for p in t["players"]["rushing"]) + t["stats"]["pass_yds"],
            )

    def test_play_by_play_only_when_asked(self):
        self.assertEqual(self.game()["log"], [])
        self.assertGreater(len(self.game(play_by_play=True)["log"]), 100)

    def test_same_seed_same_result(self):
        self.assertEqual(fs.run_for_web(self.teams, "SEA", "KC", seed=7), fs.run_for_web(self.teams, "SEA", "KC", seed=7))

    def test_sims_summary(self):
        s = json.loads(fs.run_for_web(self.teams, "SEA", "KC", seed=1, sims=60))
        self.assertEqual(s["kind"], "sims")
        self.assertEqual(s["n"], 60)
        total_wins = sum(t["wins"] for t in s["teams"]) + s["ties"]
        self.assertEqual(total_wins, 60)
        self.assertAlmostEqual(sum(t["win_pct"] for t in s["teams"]) + 100 * s["ties"] / 60, 100.0)
        self.assertEqual(len(s["common_scores"]), 3)

    def test_codes_are_case_insensitive_and_seed_is_optional(self):
        d = json.loads(fs.run_for_web(self.teams, "sea", "kc"))
        self.assertEqual([t["abbr"] for t in d["teams"]], ["SEA", "KC"])
        self.assertIsInstance(d["seed"], int)

    def test_bad_input_raises_plain_errors(self):
        with self.assertRaisesRegex(ValueError, "Unknown team XXX"):
            fs.run_for_web(self.teams, "SEA", "XXX")
        with self.assertRaisesRegex(ValueError, "two different teams"):
            fs.run_for_web(self.teams, "SEA", "SEA")


class Cli(unittest.TestCase):
    FICTIONAL = ["--teams-file", str(ROOT / "teams.json")]

    def test_unknown_team_returns_error(self):
        code, _, err = run_cli("SEA", "NOPE")
        self.assertEqual(code, 2)
        self.assertIn("Unknown team NOPE", err)

    def test_same_team_twice_returns_error(self):
        self.assertEqual(run_cli("SEA", "SEA")[0], 2)

    def test_nfl_game_runs_by_default(self):
        code, out, _ = run_cli("SEA", "KC", "--seed", "5")
        self.assertEqual(code, 0)
        self.assertIn("Seattle Seahawks", out)
        self.assertIn("Kansas City Chiefs", out)

    def test_team_codes_are_case_insensitive(self):
        self.assertEqual(run_cli("sea", "kc", "--seed", "5")[0], 0)

    def test_random_matchup_when_no_teams_given(self):
        code, out, _ = run_cli("--seed", "9")
        self.assertEqual(code, 0)
        self.assertIn("FINAL:", out)

    def test_same_seed_prints_same_game(self):
        self.assertEqual(run_cli("SEA", "KC", "--seed", "5")[1], run_cli("SEA", "KC", "--seed", "5")[1])

    def test_sims_mode(self):
        code, out, _ = run_cli("SEA", "KC", "--sims", "20", "--seed", "1")
        self.assertEqual(code, 0)
        self.assertIn("20 simulated games", out)

    def test_list_shows_32_teams(self):
        code, out, _ = run_cli("--list")
        self.assertEqual(code, 0)
        self.assertEqual(len(out.strip().splitlines()), 32)

    def test_fictional_teams_file_still_works(self):
        self.assertEqual(run_cli("TAC", "RNR", "--seed", "5", *self.FICTIONAL)[0], 0)


if __name__ == "__main__":
    unittest.main()
