#!/usr/bin/env python3
"""Build nfl_teams.json: all 32 NFL teams with ratings for footballsim.py.

Inputs (pasted below so the ratings are reproducible):
  * Starters per team from the fantasynerds.com depth chart pages, checked
    against Ourlads (Atlanta's QB was corrected to Michael Penix Jr. using
    Ourlads and a Sept 21, 2026 report). Captured Oct 18, 2026.
  * 2026 regular-season team stats from NFL.com (offense and defense,
    passing and rushing), captured Oct 18, 2026, about five games in.

Team ratings (pass_block, run_block, pass_rush, pass_defense, run_defense)
come from those stats: each stat becomes a z-score against the other 31 teams,
then rating = 70 + 6 * z, so 70 is average. Five games is a small sample, so
the scale is kept modest.

Player ratings are UNOFFICIAL estimates: a default per depth-chart slot, my
own judgment for well-known players (OVERRIDES), and a small nudge from the
team's passing and rushing efficiency. Edit the numbers freely.

    python3 tools/build_nfl_teams.py
"""

import json
import statistics
from pathlib import Path

# abbr|team|QB|RB1|RB2|WR1|WR2|WR3|TE|K
ROSTERS = """
ARI|Arizona Cardinals|Jacoby Brissett|Jeremiyah Love|Tyler Allgeier|Michael Wilson|Kendrick Bourne|Jalen Brooks|Trey McBride|Chad Ryland
ATL|Atlanta Falcons|Michael Penix Jr.|Bijan Robinson|Brian Robinson Jr.|Drake London|Jahan Dotson|Olamide Zaccheaus|Kyle Pitts|Nick Folk
BAL|Baltimore Ravens|Lamar Jackson|Derrick Henry|Justice Hill|Rashod Bateman|Ja'Kobi Lane|Zay Flowers|Mark Andrews|Tyler Loop
BUF|Buffalo Bills|Josh Allen|James Cook|Ray Davis|D.J. Moore|Josh Palmer|Khalil Shakir|Dalton Kincaid|Tyler Bass
CAR|Carolina Panthers|Bryce Young|Chuba Hubbard|AJ Dillon|Tetairoa McMillan|Brycen Tremayne|Jalen Coker|Tommy Tremble|Ryan Fitzgerald
CHI|Chicago Bears|Caleb Williams|D'Andre Swift|Kyle Monangai|Rome Odunze|Luther Burden|Kalif Raymond|Colston Loveland|Cairo Santos
CIN|Cincinnati Bengals|Joe Burrow|Chase Brown|Samaje Perine|Ja'Marr Chase|Tee Higgins|Mitchell Tinsley|Drew Sample|Evan McPherson
CLE|Cleveland Browns|Deshaun Watson|Quinshon Judkins|Raheim Sanders|Denzel Boston|Jerry Jeudy|KC Concepcion|Harold Fannin|Andre Szmyt
DAL|Dallas Cowboys|Dak Prescott|Javonte Williams|Tyler Goodson|CeeDee Lamb|George Pickens|Ryan Flournoy|Jake Ferguson|Brandon Aubrey
DEN|Denver Broncos|Bo Nix|J.K. Dobbins|RJ Harvey|Courtland Sutton|Jaylen Waddle|Troy Franklin|Evan Engram|Wil Lutz
DET|Detroit Lions|Jared Goff|Jahmyr Gibbs|Sione Vaki|Isaac TeSlaa|Jameson Williams|Amon-Ra St. Brown|Sam LaPorta|Jake Bates
GB|Green Bay Packers|Jordan Love|MarShawn Lloyd|Kaleb Johnson|Christian Watson|Matthew Golden|Skyy Moore|Tucker Kraft|Trey Smack
HOU|Houston Texans|C.J. Stroud|David Montgomery|Woody Marks|Nico Collins|Marvin Harrison Jr.|Jaylin Noel|Dalton Schultz|Ka'imi Fairbairn
IND|Indianapolis Colts|Daniel Jones|Jonathan Taylor|DJ Giddens|Ashton Dulin|Keenan Allen|Josh Downs|Tyler Warren|Spencer Shrader
JAX|Jacksonville Jaguars|Trevor Lawrence|Bhayshul Tuten|Chris Rodriguez|Brian Thomas Jr.|Jakobi Meyers|Parker Washington|Brenton Strange|Cam Little
KC|Kansas City Chiefs|Patrick Mahomes|Kenneth Walker|Emmett Johnson|Jalen Royals|Xavier Worthy|Rashee Rice|Travis Kelce|Harrison Butker
LV|Las Vegas Raiders|Kirk Cousins|Ashton Jeanty|Mike Washington Jr.|Tre Tucker|Jalen Nailor|Dareke Young|Brock Bowers|Matt Gay
LAC|Los Angeles Chargers|Justin Herbert|Omarion Hampton|Keaton Mitchell|Quentin Johnston|Tre Harris|Ladd McConkey|Charlie Kolar|Cameron Dicker
LAR|Los Angeles Rams|Matthew Stafford|Kyren Williams|Blake Corum|Davante Adams|Puka Nacua|Jordan Whittington|Colby Parkinson|Harrison Mevis
MIA|Miami Dolphins|Malik Willis|Ollie Gordon|Jaylen Wright|Chris Bell|Caleb Douglas|Malik Washington|Greg Dulcich|Riley Patterson
MIN|Minnesota Vikings|Kyler Murray|Aaron Jones|DeeJay Dallas|Justin Jefferson|Jordan Addison|Jauan Jennings|T.J. Hockenson|Will Reichard
NE|New England Patriots|Drake Maye|Rhamondre Stevenson|TreVeyon Henderson|A.J. Brown|Romeo Doubs|Demario Douglas|Hunter Henry|Andres Borregales
NO|New Orleans Saints|Tyler Shough|Travis Etienne|Alvin Kamara|Bryce Lance|Chris Olave|Devaughn Vele|Juwan Johnson|Daniel Carlson
NYG|New York Giants|Jameis Winston|Cam Skattebo|Najee Harris|Malik Nabers|Malachi Fields|Darnell Mooney|Isaiah Likely|Dominic Zvada
NYJ|New York Jets|Geno Smith|Breece Hall|Braelon Allen|Garrett Wilson|Adonai Mitchell|Isaiah Williams|Mason Taylor|Jason Sanders
PHI|Philadelphia Eagles|Jalen Hurts|Saquon Barkley|Will Shipley|DeVonta Smith|Dontayvion Wicks|Makai Lemon|Dallas Goedert|Jake Elliott
PIT|Pittsburgh Steelers|Aaron Rodgers|Jaylen Warren|Rico Dowdle|DK Metcalf|Ben Skowronek|Roman Wilson|Pat Freiermuth|Chris Boswell
SF|San Francisco 49ers|Brock Purdy|Christian McCaffrey|Kaelon Black|Mike Evans|Jacob Cowing|Deebo Samuel|George Kittle|Eddy Pineiro
SEA|Seattle Seahawks|Sam Darnold|Emanuel Wilson|George Holani|Jaxon Smith-Njigba|Rashid Shaheed|Cooper Kupp|AJ Barner|Jason Myers
TB|Tampa Bay Buccaneers|Baker Mayfield|Bucky Irving|Kenneth Gainwell|Emeka Egbuka|Ted Hurst|Chris Godwin|Cade Otton|Chase McLaughlin
TEN|Tennessee Titans|Cam Ward|Tony Pollard|Tyjae Spears|Carnell Tate|Calvin Ridley|Wan'Dale Robinson|Gunnar Helm|Joey Slye
WAS|Washington Commanders|Jayden Daniels|Jacory Croskey-Merritt|Rachaad White|Terry McLaurin|Dyami Brown|Stefon Diggs|Chigoziem Okonkwo|Drew Stevens
"""

# abbr, pass yards, attempts, completions, TD, INT, sacks taken
OFF_PASS = """
LAR 1807 252 166 11 6 10
NO 1443 235 153 12 5 13
ARI 1335 235 157 9 6 12
PIT 1487 235 143 12 5 19
HOU 1714 220 143 9 1 14
IND 1290 218 130 4 6 15
NYG 1450 213 127 11 6 18
CHI 1476 208 143 5 5 15
CAR 1549 202 121 11 2 12
PHI 1148 200 115 9 4 16
SEA 1469 198 126 11 7 16
TB 1116 194 121 5 7 22
DAL 1381 192 129 9 3 6
DET 1485 191 128 12 0 11
CIN 1361 189 135 11 3 9
DEN 1049 189 114 6 3 8
NE 1509 189 121 11 7 11
GB 1408 185 112 10 3 10
JAX 1480 184 120 14 4 10
LV 1317 180 118 12 4 8
TEN 998 177 109 4 4 10
NYJ 1336 177 122 7 1 19
CLE 1174 175 112 7 2 24
BAL 1396 168 119 9 1 14
ATL 1266 167 103 7 7 16
WAS 985 162 95 8 1 10
LAC 937 144 85 5 7 17
SF 1196 142 98 13 2 3
MIN 938 140 92 5 2 15
BUF 1249 138 91 7 4 10
MIA 849 130 73 2 4 14
KC 1037 128 82 9 2 6
"""

# abbr, rush attempts, rush yards, rush TD
OFF_RUSH = """
CHI 216 964 13
NE 187 784 4
BAL 185 909 9
ATL 177 897 8
BUF 176 893 14
LAC 169 714 4
IND 167 669 9
JAX 167 677 4
NYG 167 629 2
SEA 165 643 5
TB 161 767 5
NYJ 158 567 4
LV 157 475 3
ARI 157 578 3
CLE 155 564 3
NO 154 584 6
MIN 152 580 3
LAR 148 676 6
WAS 148 698 4
DEN 147 505 5
KC 145 799 7
HOU 142 509 6
SF 139 643 6
PHI 134 493 4
TEN 131 497 3
DET 130 571 8
MIA 130 633 5
PIT 130 595 1
CAR 128 544 5
CIN 114 414 2
DAL 107 408 7
GB 99 302 2
"""

# abbr, pass yards allowed, attempts against, completions, TD, INT, sacks
DEF_PASS = """
LAR 1043 181 104 8 5 8
NO 1536 200 133 10 4 15
ARI 1484 172 113 16 3 14
PIT 1332 201 124 6 6 16
LV 1521 193 123 13 4 15
HOU 1587 218 143 10 3 18
IND 1442 189 116 10 2 10
NYG 1192 191 121 12 6 8
CHI 1368 163 102 9 3 17
CAR 1185 189 114 6 3 11
PHI 1523 217 131 8 3 8
SEA 941 180 114 8 7 16
TB 1426 215 143 9 6 11
DAL 1159 140 101 10 0 5
DET 1607 213 145 14 3 20
CIN 1225 168 105 5 3 17
DEN 1380 216 122 7 7 18
NE 1365 192 127 7 4 14
GB 997 157 102 6 7 14
JAX 1698 212 140 7 7 11
LAC 1025 141 91 7 4 11
TEN 1412 188 130 6 4 16
NYJ 1212 192 118 9 1 17
CLE 1364 206 123 11 4 19
BUF 1792 242 157 15 3 11
BAL 1354 197 128 5 3 15
ATL 1612 246 159 10 1 15
WAS 1344 190 124 14 3 9
KC 916 147 90 4 4 4
SF 1054 174 112 5 3 11
MIN 977 156 83 3 6 17
MIA 1130 145 111 11 3 4
"""

# abbr, rush attempts against, rush yards allowed, rush TD allowed
DEF_RUSH = """
CHI 121 543 5
NE 140 551 5
BAL 158 603 7
ATL 139 499 6
IND 154 735 6
JAX 134 433 4
NYG 161 813 6
SEA 164 576 4
TB 133 453 2
NYJ 176 738 4
CLE 154 674 1
NO 173 828 11
MIN 108 433 2
WAS 122 477 3
BUF 138 541 5
DEN 180 839 6
LAC 158 593 7
HOU 145 498 5
SF 133 488 3
LV 135 703 6
PHI 181 716 8
TEN 191 735 6
DET 126 535 6
MIA 151 553 4
PIT 153 619 4
CAR 129 661 8
LAR 140 642 4
ARI 144 633 6
KC 104 371 3
CIN 122 615 5
DAL 165 842 6
GB 157 638 8
"""

# Defaults by depth-chart slot, then my own estimates for notable players.
DEFAULTS = {"qb": 70, "rb1": 70, "rb2": 66, "wr1": 72, "wr2": 69, "wr3": 66, "te": 68, "k": 74}

OVERRIDES = {
    # quarterbacks
    "Patrick Mahomes": 82, "Josh Allen": 83, "Lamar Jackson": 83, "Joe Burrow": 80, "Jalen Hurts": 77,
    "Jared Goff": 77, "Dak Prescott": 77, "Justin Herbert": 77, "Matthew Stafford": 78, "C.J. Stroud": 74,
    "Jordan Love": 77, "Brock Purdy": 75, "Jayden Daniels": 77, "Drake Maye": 76, "Caleb Williams": 73,
    "Bo Nix": 74, "Baker Mayfield": 74, "Sam Darnold": 74, "Kyler Murray": 75, "Trevor Lawrence": 74,
    "Michael Penix Jr.": 71, "Bryce Young": 70, "Cam Ward": 69, "Aaron Rodgers": 72, "Geno Smith": 69,
    "Daniel Jones": 69, "Kirk Cousins": 67, "Jacoby Brissett": 67, "Jameis Winston": 66,
    "Deshaun Watson": 66, "Malik Willis": 68, "Tyler Shough": 69,
    # running backs
    "Saquon Barkley": 84, "Bijan Robinson": 85, "Jahmyr Gibbs": 85, "Derrick Henry": 80,
    "Jonathan Taylor": 83, "Christian McCaffrey": 80, "Breece Hall": 76, "James Cook": 79,
    "Ashton Jeanty": 79, "Kenneth Walker": 78, "Chase Brown": 74, "D'Andre Swift": 74, "Aaron Jones": 74,
    "Travis Etienne": 74, "Alvin Kamara": 72, "Omarion Hampton": 76, "Jaylen Warren": 73,
    "Kyren Williams": 73, "Chuba Hubbard": 73, "Bucky Irving": 75, "Tony Pollard": 72, "J.K. Dobbins": 74,
    "David Montgomery": 73, "Javonte Williams": 72, "Quinshon Judkins": 74, "Jeremiyah Love": 75,
    "Cam Skattebo": 74, "Rhamondre Stevenson": 71, "TreVeyon Henderson": 73, "Tyler Allgeier": 70,
    # wide receivers
    "Ja'Marr Chase": 87, "Justin Jefferson": 87, "CeeDee Lamb": 86, "Puka Nacua": 87,
    "Jaxon Smith-Njigba": 86, "Amon-Ra St. Brown": 84, "Nico Collins": 83, "Malik Nabers": 82,
    "Drake London": 82, "Garrett Wilson": 80, "A.J. Brown": 83, "DeVonta Smith": 80, "Terry McLaurin": 79,
    "Davante Adams": 79, "Tee Higgins": 80, "Brian Thomas Jr.": 80, "Ladd McConkey": 80,
    "Tetairoa McMillan": 78, "Rome Odunze": 78, "Zay Flowers": 79, "DK Metcalf": 78, "George Pickens": 80,
    "Courtland Sutton": 77, "Jaylen Waddle": 78, "Mike Evans": 78, "Khalil Shakir": 76, "D.J. Moore": 76,
    "Chris Olave": 77, "Emeka Egbuka": 78, "Marvin Harrison Jr.": 76, "Xavier Worthy": 75,
    "Rashee Rice": 78, "Jakobi Meyers": 75, "Keenan Allen": 72, "Deebo Samuel": 73, "Cooper Kupp": 74,
    "Jameson Williams": 77, "Calvin Ridley": 74, "Jerry Jeudy": 74, "Christian Watson": 74,
    "Quentin Johnston": 74, "Rashod Bateman": 73, "Jordan Addison": 74, "Jauan Jennings": 74,
    "Stefon Diggs": 72,
    # tight ends
    "Brock Bowers": 86, "Trey McBride": 86, "George Kittle": 84, "Travis Kelce": 78, "Sam LaPorta": 80,
    "Mark Andrews": 78, "T.J. Hockenson": 77, "Dallas Goedert": 76, "Tucker Kraft": 77,
    "Dalton Kincaid": 75, "Kyle Pitts": 76, "Jake Ferguson": 74, "Colston Loveland": 76,
    "Tyler Warren": 78, "Hunter Henry": 75, "Pat Freiermuth": 75, "Dalton Schultz": 73,
    "Evan Engram": 73, "Harold Fannin": 75, "Mason Taylor": 72, "Isaiah Likely": 73,
    "Drew Sample": 66,
    # kickers
    "Brandon Aubrey": 92, "Harrison Butker": 84, "Jake Bates": 82, "Chris Boswell": 84, "Cam Little": 86,
    "Jason Myers": 78, "Cameron Dicker": 82, "Tyler Bass": 80, "Evan McPherson": 82, "Jake Elliott": 80,
    "Ka'imi Fairbairn": 80, "Daniel Carlson": 82, "Chase McLaughlin": 80, "Will Reichard": 78,
    "Cairo Santos": 78, "Wil Lutz": 78, "Tyler Loop": 78, "Jason Sanders": 78, "Dominic Zvada": 77,
    "Nick Folk": 74, "Joey Slye": 74, "Matt Gay": 76, "Chad Ryland": 76,
}


def table(text, width):
    rows = {}
    for line in text.strip().splitlines():
        parts = line.split()
        rows[parts[0]] = [int(x) for x in parts[1:]]
        assert len(parts) == width + 1, line
    return rows


def zscores(values):
    mean = statistics.fmean(values.values())
    sd = statistics.pstdev(values.values())
    return {k: (v - mean) / sd for k, v in values.items()}


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def rating(z, scale=6):
    return int(clamp(round(70 + scale * z), 45, 95))


def main():
    rosters = {}
    for line in ROSTERS.strip().splitlines():
        abbr, name, *players = line.split("|")
        assert len(players) == 8, line
        rosters[abbr] = (name, players)
    off_pass, off_rush = table(OFF_PASS, 6), table(OFF_RUSH, 3)
    def_pass, def_rush = table(DEF_PASS, 6), table(DEF_RUSH, 3)
    teams = list(rosters)
    for t in (off_pass, off_rush, def_pass, def_rush):
        assert set(t) == set(teams), set(teams) ^ set(t)

    z_sack_taken = zscores({a: off_pass[a][5] / (off_pass[a][1] + off_pass[a][5]) for a in teams})
    z_off_ypc = zscores({a: off_rush[a][1] / off_rush[a][0] for a in teams})
    z_off_ypa = zscores({a: off_pass[a][0] / off_pass[a][1] for a in teams})
    z_sack_made = zscores({a: def_pass[a][5] / (def_pass[a][1] + def_pass[a][5]) for a in teams})
    z_def_ypa = zscores({a: def_pass[a][0] / def_pass[a][1] for a in teams})
    z_def_int = zscores({a: def_pass[a][4] / def_pass[a][1] for a in teams})
    z_def_ypc = zscores({a: def_rush[a][1] / def_rush[a][0] for a in teams})

    def player(slot, name, nudge, pos=None):
        value = OVERRIDES.get(name, DEFAULTS[slot]) + nudge
        entry = {"name": name, "rating": int(clamp(round(value), 50, 95))}
        if pos:
            entry["pos"] = pos
        return entry

    out = {}
    for a in teams:
        name, (qb, rb1, rb2, wr1, wr2, wr3, te, k) = rosters[a]
        pass_nudge, run_nudge = z_off_ypa[a], z_off_ypc[a]
        out[a] = {
            "name": name,
            "pass_block": rating(-z_sack_taken[a]),
            "run_block": rating(z_off_ypc[a]),
            "pass_rush": rating(z_sack_made[a]),
            "pass_defense": rating(-0.7 * z_def_ypa[a] + 0.3 * z_def_int[a]),
            "run_defense": rating(-z_def_ypc[a]),
            "players": {
                "qb": player("qb", qb, 3 * pass_nudge),
                "rbs": [player("rb1", rb1, 2 * run_nudge), player("rb2", rb2, 2 * run_nudge)],
                "receivers": [
                    player("wr1", wr1, 2 * pass_nudge, "WR"),
                    player("wr2", wr2, 2 * pass_nudge, "WR"),
                    player("wr3", wr3, 2 * pass_nudge, "WR"),
                    player("te", te, 0, "TE"),
                ],
                "kicker": player("k", k, 0),
            },
        }

    data = {
        "source": "Starters: fantasynerds.com depth charts (checked against Ourlads). Team stats: NFL.com 2026 "
                  "regular season, captured Oct 18, 2026. Ratings are unofficial estimates; see "
                  "tools/build_nfl_teams.py.",
        "teams": out,
    }
    path = Path(__file__).resolve().parent.parent / "nfl_teams.json"
    path.write_text(json.dumps(data, indent=1) + "\n")
    print(f"wrote {path} ({len(out)} teams)")


if __name__ == "__main__":
    main()
