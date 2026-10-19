#!/usr/bin/env python3
"""Football game simulator.

Simulates an American football game play by play, then prints the final
score, team stats and player stats. Run many games with --sims to see win
odds and average scores. Teams and player ratings live in teams.json.

    python3 footballsim.py TAC RNR
    python3 footballsim.py TAC RNR --seed 42 --play-by-play
    python3 footballsim.py TAC RNR --sims 1000
"""

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

QUARTER = 900  # seconds
HALF = 2 * QUARTER
REGULATION = 4 * QUARTER
OVERTIME = 600
POS_WEIGHT = {"WR": 1.0, "TE": 0.75, "RB": 0.5}
RATING_KEYS = ("pass_block", "run_block", "pass_rush", "pass_defense", "run_defense")


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


# ---------------------------------------------------------------- team data


def check_rating(value, label):
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= 100:
        raise ValueError(f"{label} must be a whole number from 1 to 100, got {value!r}")
    return value


def check_player(p, abbr):
    if not isinstance(p, dict) or "name" not in p or "rating" not in p:
        raise ValueError(f"team {abbr}: every player needs a name and a rating")
    check_rating(p["rating"], f"{abbr} {p['name']} rating")
    return p


class Team:
    def __init__(self, abbr, d):
        self.abbr = abbr
        try:
            self.name = d["name"]
            for key in RATING_KEYS:
                setattr(self, key, check_rating(d[key], f"{abbr}.{key}"))
            p = d["players"]
            self.qb = check_player(p["qb"], abbr)
            self.rbs = [check_player(x, abbr) for x in p["rbs"]]
            self.receivers = [check_player(x, abbr) for x in p["receivers"]]
            self.kicker = check_player(p["kicker"], abbr)
        except KeyError as e:
            raise ValueError(f"team {abbr} is missing {e}") from None
        if not self.rbs:
            raise ValueError(f"team {abbr} needs at least one running back")
        if not self.receivers:
            raise ValueError(f"team {abbr} needs at least one receiver")
        for rec in self.receivers:
            if rec.get("pos") not in ("WR", "TE"):
                raise ValueError(f"team {abbr}: receiver {rec['name']} needs pos WR or TE")
        # Pass targets: receivers plus the lead back (a checkdown option).
        self.targets = self.receivers + [dict(self.rbs[0], pos="RB")]


def load_teams(path):
    data = json.loads(Path(path).read_text())
    return {abbr: Team(abbr, t) for abbr, t in data["teams"].items()}


# --------------------------------------------------------------- simulation


class Game:
    def __init__(self, a, b, seed=None):
        self.seed = seed
        self.rng = random.Random(seed)
        self.teams = {a.abbr: a, b.abbr: b}
        self.order = [a.abbr, b.abbr]
        self.points = {k: 0 for k in self.order}
        self.quarters = {k: [0] * 5 for k in self.order}
        self.pstats = {k: defaultdict(lambda: defaultdict(int)) for k in self.order}
        self.tstats = {k: defaultdict(int) for k in self.order}
        self.log = []
        self.elapsed = 0
        self.ot = False
        self.half_done = False
        self.poss = None
        self.yl = 0  # yards from the possessing team's own goal line (100 = end zone)
        self.down = 1
        self.to_go = 10
        self.ctx = ""

    # -- small helpers

    def other(self, abbr):
        return self.order[1] if abbr == self.order[0] else self.order[0]

    def quarter(self):
        return 5 if self.ot else min(4, self.elapsed // QUARTER + 1)

    def clock_text(self):
        if self.ot:
            left = REGULATION + OVERTIME - self.elapsed
        else:
            left = QUARTER - self.elapsed % QUARTER
        return f"{left // 60}:{left % 60:02d}"

    def field_text(self):
        return f"own {self.yl}" if self.yl <= 50 else f"opp {100 - self.yl}"

    def say(self, text):
        self.log.append(f"{self.ctx} - {text}")

    def note(self, text):
        self.log.append(text)

    def give_ball(self, team, yl):
        self.poss = team
        self.yl = int(yl)
        self.down = 1
        self.to_go = min(10, 100 - self.yl)

    def kick_start(self):
        return clamp(int(self.rng.gauss(27, 5)), 12, 45)

    def add_points(self, team, pts, q):
        self.points[team] += pts
        self.quarters[team][q - 1] += pts

    def turnover(self, new_yl):
        self.tstats[self.poss]["turnovers"] += 1
        self.give_ball(self.other(self.poss), new_yl)

    def advance(self, secs):
        """Run the clock. Call before possession changes."""
        if self.ot:
            limit = REGULATION + OVERTIME
        elif self.half_done:
            limit = REGULATION
        else:
            limit = HALF
        trailing = self.points[self.poss] < self.points[self.other(self.poss)]
        if not self.ot:
            hurry_half = HALF - 120 <= self.elapsed < HALF
            hurry_game = self.elapsed >= REGULATION - 150 and trailing
            if hurry_half or hurry_game:
                secs = max(4, secs // 2)
        self.elapsed = min(limit, self.elapsed + secs)

    def spot(self, yards):
        """Apply a normal (non-scoring, non-turnover) play result."""
        old = self.yl
        self.yl = clamp(old + yards, 1, 99)
        gained = self.yl - old
        if gained >= self.to_go:
            self.tstats[self.poss]["first_downs"] += 1
            self.down = 1
            self.to_go = min(10, 100 - self.yl)
            return
        self.down += 1
        self.to_go -= gained
        if self.down > 4:
            self.say("Turnover on downs")
            self.tstats[self.poss]["downs"] += 1
            self.give_ball(self.other(self.poss), 100 - self.yl)

    def gain(self, yards):
        """Yards actually gained once the field limits are applied."""
        return clamp(self.yl + yards, 1, 99) - self.yl

    # -- play calling

    def pass_prob(self, abbr):
        p = 0.50
        diff = self.points[abbr] - self.points[self.other(abbr)]
        remaining = REGULATION - self.elapsed
        if not self.ot and self.elapsed >= 3 * QUARTER:
            if diff < -8:
                p += 0.25
            elif diff < 0:
                p += 0.10
            elif diff > 0 and remaining < 420:
                p -= 0.25
        if self.to_go >= 8:
            p += 0.12
        elif self.to_go <= 2:
            p -= 0.25
        return clamp(p, 0.10, 0.90)

    def fourth_down_choice(self, off):
        goal = 100 - self.yl
        deficit = self.points[self.other(off.abbr)] - self.points[off.abbr]
        if not self.ot and self.elapsed >= REGULATION - 120 and deficit > 3:
            return "go"
        if goal <= 38:
            return "fg"
        if self.to_go <= 2 and self.yl >= 45:
            return "go"
        return "punt"

    def play(self):
        off = self.teams[self.poss]
        deff = self.teams[self.other(self.poss)]
        q = self.quarter()
        label = "OT" if q == 5 else f"Q{q}"
        self.ctx = f"{label} {self.clock_text()} {off.abbr} {self.down}&{self.to_go} at {self.field_text()}"
        if self.down == 4:
            choice = self.fourth_down_choice(off)
            if choice == "fg":
                return self.field_goal(off, q)
            if choice == "punt":
                return self.punt(off, deff)
        self.tstats[off.abbr]["plays"] += 1
        if self.rng.random() < self.pass_prob(off.abbr):
            self.pass_play(off, deff, q)
        else:
            self.run_play(off, deff, q)

    # -- play types

    def touchdown(self, off, q, text):
        self.add_points(off.abbr, 6, q)
        self.say(f"{text} - TOUCHDOWN {off.abbr}")
        if not self.ot:
            self.extra_point(off, q)
        self.give_ball(self.other(off.abbr), self.kick_start())

    def extra_point(self, off, q):
        k = off.kicker
        ks = self.pstats[off.abbr][k["name"]]
        p = clamp(0.94 + (k["rating"] - 75) * 0.001, 0.8, 0.99)
        ks["xp_att"] += 1
        if self.rng.random() < p:
            ks["xp_made"] += 1
            self.add_points(off.abbr, 1, q)
            self.say(f"{k['name']} extra point is good")
        else:
            self.say(f"{k['name']} extra point is no good")

    def field_goal(self, off, q):
        r = self.rng
        k = off.kicker
        ks = self.pstats[off.abbr][k["name"]]
        dist = 100 - self.yl + 17
        p = clamp(0.99 - (dist - 20) * 0.0085 + (k["rating"] - 75) * 0.002, 0.2, 0.995)
        ks["fg_att"] += 1
        self.advance(r.randint(6, 12))
        if r.random() < p:
            ks["fg_made"] += 1
            ks["fg_long"] = max(ks["fg_long"], dist)
            self.add_points(off.abbr, 3, q)
            self.say(f"{k['name']} {dist}-yd field goal is good")
            self.give_ball(self.other(off.abbr), self.kick_start())
        else:
            self.say(f"{k['name']} {dist}-yd field goal is no good")
            self.give_ball(self.other(off.abbr), max(20, 107 - self.yl))

    def punt(self, off, deff):
        r = self.rng
        self.tstats[off.abbr]["punts"] += 1
        net = clamp(int(r.gauss(44, 7)), 25, 70)
        landing = self.yl + net
        self.advance(r.randint(8, 14))
        if landing >= 100:
            self.say(f"{off.abbr} punts into the end zone, touchback")
            self.give_ball(deff.abbr, 20)
        else:
            self.say(f"{off.abbr} punts {net} yds")
            self.give_ball(deff.abbr, 100 - landing)

    def pass_play(self, off, deff, q):
        r = self.rng
        qb = off.qb
        qs = self.pstats[off.abbr][qb["name"]]
        sack_p = clamp(0.055 + (deff.pass_rush - off.pass_block) * 0.0008, 0.02, 0.12)
        if r.random() < sack_p:
            loss = min(r.randint(3, 10), self.yl - 1)
            self.advance(r.randint(28, 40))
            qs["sacked"] += 1
            qs["sack_yds"] += loss
            self.tstats[deff.abbr]["sacks"] += 1
            self.say(f"{qb['name']} sacked for a loss of {loss}")
            self.spot(-loss)
            return

        weights = [POS_WEIGHT[t["pos"]] * (t["rating"] / 70) ** 2 for t in off.targets]
        target = r.choices(off.targets, weights)[0]
        ts = self.pstats[off.abbr][target["name"]]
        qs["pass_att"] += 1
        ts["targets"] += 1

        int_p = clamp(0.031 + (deff.pass_defense - qb["rating"]) * 0.0006, 0.008, 0.06)
        if r.random() < int_p:
            self.advance(r.randint(6, 10))
            qs["interceptions"] += 1
            self.tstats[deff.abbr]["interceptions"] += 1
            spot = self.yl + r.randint(5, 25)
            new_yl = 20 if spot >= 100 else 100 - spot
            self.say(f"{qb['name']} pass for {target['name']} intercepted")
            self.turnover(new_yl)
            return

        comp_p = clamp(
            0.645
            + ((qb["rating"] - 70) + 0.5 * (target["rating"] - 70) - (deff.pass_defense - 70)) * 0.003,
            0.45,
            0.82,
        )
        if r.random() >= comp_p:
            self.advance(r.randint(6, 10))
            self.say(f"{qb['name']} pass to {target['name']} incomplete")
            self.spot(0)
            return

        yards = int(round(r.gauss(9.4, 5.5)))
        if r.random() < 0.05:
            yards += r.randint(15, 40)
        yards = max(yards, -2)
        self.advance(r.randint(24, 38))
        if self.yl + yards >= 100:
            yards = 100 - self.yl
            qs["pass_comp"] += 1
            qs["pass_yds"] += yards
            qs["pass_td"] += 1
            ts["rec"] += 1
            ts["rec_yds"] += yards
            ts["rec_td"] += 1
            self.touchdown(off, q, f"{qb['name']} pass to {target['name']} for {yards} yds")
            return
        yards = self.gain(yards)
        qs["pass_comp"] += 1
        qs["pass_yds"] += yards
        ts["rec"] += 1
        ts["rec_yds"] += yards
        self.say(f"{qb['name']} pass to {target['name']} for {yards} yds")
        self.spot(yards)

    def run_play(self, off, deff, q):
        r = self.rng
        scramble = r.random() < 0.06
        if scramble:
            carrier, base = off.qb, 4.6
        else:
            carrier = off.rbs[0] if len(off.rbs) == 1 or r.random() < 0.65 else off.rbs[1]
            base = 3.4
        mean = base + (off.run_block - deff.run_defense) * 0.03 + (carrier["rating"] - 70) * 0.03
        yards = int(round(r.gauss(mean, 3.0)))
        if r.random() < 0.04:
            yards += r.randint(10, 45)
        yards = max(yards, -4)
        cs = self.pstats[off.abbr][carrier["name"]]
        cs["rush_att"] += 1
        self.advance(r.randint(30, 44))
        verb = "scrambles" if scramble else "rushes"

        if r.random() < 0.012:
            gained = self.gain(yards)
            cs["rush_yds"] += gained
            cs["fumbles"] += 1
            self.say(f"{carrier['name']} {verb} for {gained} yds and fumbles, defense recovers")
            self.turnover(100 - (self.yl + gained))
            return
        if self.yl + yards >= 100:
            yards = 100 - self.yl
            cs["rush_yds"] += yards
            cs["rush_td"] += 1
            self.touchdown(off, q, f"{carrier['name']} {verb} for {yards} yds")
            return
        yards = self.gain(yards)
        cs["rush_yds"] += yards
        self.say(f"{carrier['name']} {verb} for {yards} yds")
        self.spot(yards)

    # -- whole game

    def run(self):
        first = self.rng.choice(self.order)
        self.note(f"Opening kickoff: {first} receives")
        self.give_ball(first, self.kick_start())
        while self.elapsed < REGULATION:
            self.play()
            if not self.half_done and self.elapsed >= HALF:
                self.half_done = True
                self.note("--- Halftime ---")
                self.give_ball(self.other(first), self.kick_start())
        if self.points[self.order[0]] == self.points[self.order[1]]:
            self.overtime()
        return self

    def overtime(self):
        self.ot = True
        self.elapsed = REGULATION
        limit = REGULATION + OVERTIME
        self.note("--- Overtime (sudden death, simplified) ---")
        self.give_ball(self.rng.choice(self.order), self.kick_start())
        while self.elapsed < limit:
            before = dict(self.points)
            self.play()
            if self.points != before:
                break

    def winner(self):
        a, b = self.order
        if self.points[a] == self.points[b]:
            return None
        return a if self.points[a] > self.points[b] else b

    def totals(self, abbr):
        players = self.pstats[abbr].values()
        t = self.tstats[abbr]
        rush = sum(p["rush_yds"] for p in players)
        gross = sum(p["pass_yds"] for p in players)
        sack_yds = sum(p["sack_yds"] for p in players)
        return {
            "plays": t["plays"],
            "rush_yds": rush,
            "pass_yds": gross - sack_yds,
            "total_yds": rush + gross - sack_yds,
            "first_downs": t["first_downs"],
            "turnovers": t["turnovers"],
            "sacks": t["sacks"],
        }


# ---------------------------------------------------------------- reporting


def table(title, header, rows):
    cols = list(zip(header, *rows))
    widths = [max(len(str(c)) for c in col) for col in cols]

    def fmt(row):
        cells = [str(row[0]).ljust(widths[0])]
        cells += [str(v).rjust(w) for v, w in zip(row[1:], widths[1:])]
        return "  ".join(cells)

    return "\n".join([title, fmt(header), *[fmt(r) for r in rows]])


def player_tables(game, abbr):
    team = game.teams[abbr]
    ps = game.pstats[abbr]
    out = []

    qb = ps[team.qb["name"]]
    if qb["pass_att"] or qb["sacked"]:
        out.append(
            table(
                f"{team.name} - passing",
                ["Player", "C/ATT", "YDS", "TD", "INT", "SACKED"],
                [[team.qb["name"], f"{qb['pass_comp']}/{qb['pass_att']}", qb["pass_yds"],
                  qb["pass_td"], qb["interceptions"], qb["sacked"]]],
            )
        )

    rushers = sorted((n for n, s in ps.items() if s["rush_att"]), key=lambda n: -ps[n]["rush_yds"])
    if rushers:
        rows = []
        for n in rushers:
            s = ps[n]
            rows.append([n, s["rush_att"], s["rush_yds"], f"{s['rush_yds'] / s['rush_att']:.1f}",
                         s["rush_td"], s["fumbles"]])
        out.append(table(f"{team.name} - rushing", ["Player", "ATT", "YDS", "AVG", "TD", "FUM"], rows))

    catchers = sorted((n for n, s in ps.items() if s["targets"]), key=lambda n: -ps[n]["rec_yds"])
    if catchers:
        rows = [[n, ps[n]["targets"], ps[n]["rec"], ps[n]["rec_yds"], ps[n]["rec_td"]] for n in catchers]
        out.append(table(f"{team.name} - receiving", ["Player", "TGT", "REC", "YDS", "TD"], rows))

    k = ps[team.kicker["name"]]
    if k["fg_att"] or k["xp_att"]:
        out.append(
            table(
                f"{team.name} - kicking",
                ["Player", "FG", "LONG", "XP"],
                [[team.kicker["name"], f"{k['fg_made']}/{k['fg_att']}", k["fg_long"] or "-",
                  f"{k['xp_made']}/{k['xp_att']}"]],
            )
        )
    return out


def render_game(game, play_by_play=False):
    a, b = game.order
    ta, tb = game.teams[a], game.teams[b]
    lines = []
    if play_by_play:
        lines += game.log + [""]

    suffix = " (OT)" if game.ot else ""
    lines.append(f"FINAL: {ta.name} {game.points[a]}, {tb.name} {game.points[b]}{suffix}")
    lines.append("")

    header = ["", "1", "2", "3", "4"] + (["OT"] if game.ot else []) + ["T"]
    width = 5 if game.ot else 4
    rows = [[k] + game.quarters[k][:width] + [game.points[k]] for k in game.order]
    lines.append(table("Line score", header, rows))
    lines.append("")

    sa, sb = game.totals(a), game.totals(b)
    ypp = lambda s: f"{s['total_yds'] / s['plays']:.1f}" if s["plays"] else "0.0"
    rows = [
        ["Total yards", sa["total_yds"], sb["total_yds"]],
        ["Passing yards (net)", sa["pass_yds"], sb["pass_yds"]],
        ["Rushing yards", sa["rush_yds"], sb["rush_yds"]],
        ["Plays", sa["plays"], sb["plays"]],
        ["Yards per play", ypp(sa), ypp(sb)],
        ["First downs", sa["first_downs"], sb["first_downs"]],
        ["Turnovers", sa["turnovers"], sb["turnovers"]],
        ["Sacks (by defense)", sa["sacks"], sb["sacks"]],
    ]
    lines.append(table("Team stats", ["", a, b], rows))

    for abbr in game.order:
        for t in player_tables(game, abbr):
            lines += ["", t]
    lines += ["", f"Seed: {game.seed} (rerun with --seed {game.seed} for the same game)"]
    return "\n".join(lines)


def render_sims(teams, a, b, n, seed):
    wins = Counter()
    pts = Counter()
    pass_y = Counter()
    rush_y = Counter()
    scores = Counter()
    for i in range(n):
        g = Game(teams[a], teams[b], seed=seed + i).run()
        wins[g.winner()] += 1
        for k in (a, b):
            t = g.totals(k)
            pts[k] += g.points[k]
            pass_y[k] += t["pass_yds"]
            rush_y[k] += t["rush_yds"]
        scores[(g.points[a], g.points[b])] += 1

    rows = []
    for k in (a, b):
        rows.append([f"{teams[k].name} ({k})", f"{100 * wins[k] / n:.1f}%", f"{pts[k] / n:.1f}",
                     f"{pass_y[k] / n:.0f}", f"{rush_y[k] / n:.0f}"])
    out = [f"{n} simulated games, {a} vs {b} (seeds {seed} to {seed + n - 1})", ""]
    out.append(table("Results", ["Team", "Win %", "Avg pts", "Avg pass yds", "Avg rush yds"], rows))
    if wins[None]:
        out.append(f"Ties: {wins[None]} ({100 * wins[None] / n:.1f}%)")
    common = ", ".join(f"{a} {x}-{y} {b} (x{c})" for (x, y), c in scores.most_common(3))
    out += ["", f"Most common final scores: {common}"]
    return "\n".join(out)


# ---------------------------------------------------------------------- CLI


def main(argv=None):
    ap = argparse.ArgumentParser(description="Simulate a football game: final score and player stats.")
    ap.add_argument("teams", nargs="*", help="two team abbreviations, e.g. TAC RNR (default: first two in the file)")
    ap.add_argument("--teams-file", default=str(Path(__file__).with_name("teams.json")))
    ap.add_argument("--seed", type=int, help="seed for a repeatable game")
    ap.add_argument("--sims", type=int, default=0, help="simulate N games and show win odds and averages")
    ap.add_argument("--play-by-play", action="store_true", help="print every play")
    ap.add_argument("--list", action="store_true", help="list available teams and exit")
    args = ap.parse_args(argv)

    try:
        teams = load_teams(args.teams_file)
    except (OSError, ValueError, json.JSONDecodeError) as e:
        print(f"Could not load teams: {e}", file=sys.stderr)
        return 2

    if args.list:
        for abbr, t in teams.items():
            print(f"{abbr}  {t.name}  (QB {t.qb['name']} {t.qb['rating']})")
        return 0

    picks = [x.upper() for x in args.teams] or list(teams)[:2]
    if len(picks) != 2 or picks[0] == picks[1]:
        print("Pick two different teams, e.g.: footballsim.py TAC RNR", file=sys.stderr)
        return 2
    for p in picks:
        if p not in teams:
            print(f"Unknown team {p}. Available: {', '.join(teams)}", file=sys.stderr)
            return 2
    a, b = picks

    seed = args.seed if args.seed is not None else random.randrange(1_000_000)
    if args.sims > 0:
        print(render_sims(teams, a, b, args.sims, seed))
    else:
        game = Game(teams[a], teams[b], seed=seed).run()
        print(render_game(game, args.play_by_play))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:  # e.g. output piped into `head`
        sys.exit(0)
