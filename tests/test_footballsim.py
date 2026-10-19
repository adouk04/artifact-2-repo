"""Tests for footballsim. Run from the repo root:

    python3 -m unittest discover -s tests -v
"""

import copy
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


class Cli(unittest.TestCase):
    def test_unknown_team_returns_error(self):
        self.assertEqual(fs.main(["TAC", "NOPE"]), 2)

    def test_same_team_twice_returns_error(self):
        self.assertEqual(fs.main(["TAC", "TAC"]), 2)

    def test_single_game_runs(self):
        self.assertEqual(fs.main(["TAC", "RNR", "--seed", "5"]), 0)


if __name__ == "__main__":
    unittest.main()
