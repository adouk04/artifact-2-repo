/* Page logic for the NFL game simulator. The game itself is played by
   footballsim.py, which worker.js runs in the browser with Pyodide. */

const $ = (selector) => document.querySelector(selector);

const teamA = $("#team-a");
const teamB = $("#team-b");
const seedInput = $("#seed");
const pbpInput = $("#pbp");
const playOne = $("#play-one");
const playMany = $("#play-many");
const randomButton = $("#random");
const statusLine = $("#status");
const result = $("#result");

const SIM_GAMES = 1000;

let teams = [];
let engineReady = false;
let busy = false;
let autorun = null;

const worker = new Worker("worker.js");
let nextId = 1;
const pending = new Map();

worker.onmessage = (event) => {
  const msg = event.data;
  if (msg.type === "status") {
    setStatus(msg.text);
  } else if (msg.type === "ready") {
    engineReady = true;
    setStatus("Ready.");
    updateControls();
    if (autorun) {
      const run = autorun;
      autorun = null;
      play(run.sims);
    }
  } else if (msg.type === "fatal") {
    setStatus(`The simulator could not load: ${msg.message}. Check your connection and reload the page.`, true);
  } else if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id);
    pending.delete(msg.id);
    if (msg.error) reject(new Error(msg.error));
    else resolve(msg.result);
  }
};

worker.onerror = (event) => {
  const why = event && event.message ? ` (${event.message})` : "";
  setStatus(`The simulator could not start${why}. If you opened this file directly, serve the folder with a web server instead (see the README).`, true);
};

function callEngine(request) {
  return new Promise((resolve, reject) => {
    const id = nextId++;
    pending.set(id, { resolve, reject });
    worker.postMessage({ id, ...request });
  });
}

/* ---------- helpers ---------- */

const escapeHtml = (value) =>
  String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const number = (value, digits = 0) =>
  Number(value).toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });

function setStatus(text, isError = false) {
  statusLine.textContent = text;
  statusLine.classList.toggle("error", isError);
}

function updateControls() {
  const ready = engineReady && teams.length > 0 && !busy;
  playOne.disabled = !ready;
  playMany.disabled = !ready;
  randomButton.disabled = !(teams.length > 0 && !busy);
}

function reducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/* ---------- teams ---------- */

function fillSelect(select, value) {
  select.innerHTML = teams
    .map((t) => `<option value="${escapeHtml(t.abbr)}">${escapeHtml(t.name)}</option>`)
    .join("");
  if (value) select.value = value;
}

function randomMatchup() {
  const first = Math.floor(Math.random() * teams.length);
  let second = Math.floor(Math.random() * (teams.length - 1));
  if (second >= first) second += 1;
  teamA.value = teams[first].abbr;
  teamB.value = teams[second].abbr;
}

async function loadTeams() {
  try {
    const response = await fetch("nfl_teams.json");
    if (!response.ok) throw new Error(`status ${response.status}`);
    const data = await response.json();
    teams = Object.entries(data.teams)
      .map(([abbr, t]) => ({ abbr, name: t.name }))
      .sort((x, y) => x.name.localeCompare(y.name));
  } catch (err) {
    setStatus("Could not load the team list. If you opened this file directly, serve the folder with a web server instead (see the README).", true);
    return;
  }

  fillSelect(teamA);
  fillSelect(teamB);
  teamA.disabled = false;
  teamB.disabled = false;

  const params = new URLSearchParams(location.search);
  const known = (abbr) => teams.some((t) => t.abbr === abbr);
  const a = (params.get("a") || "").toUpperCase();
  const b = (params.get("b") || "").toUpperCase();
  if (known(a) && known(b) && a !== b) {
    teamA.value = a;
    teamB.value = b;
    seedInput.value = params.get("seed") || "";
    autorun = { sims: params.get("sims") ? SIM_GAMES : 0 };
  } else {
    randomMatchup();
  }
  setStatus(engineReady ? "Ready." : "Loading Python (about 10 MB the first time)…");
  updateControls();
}

/* ---------- playing ---------- */

async function play(sims) {
  if (busy) return;
  const a = teamA.value;
  const b = teamB.value;
  if (a === b) {
    showError("Pick two different teams.");
    return;
  }

  busy = true;
  updateControls();
  setStatus(sims ? `Playing ${number(sims)} games…` : "Playing…");

  try {
    const data = await callEngine({ a, b, seed: seedInput.value.trim(), pbp: pbpInput.checked, sims });
    if (data.kind === "error") {
      showError(data.message);
    } else {
      render(data);
      rememberInUrl(a, b, data, sims);
      setStatus("Ready.");
    }
  } catch (err) {
    showError(err.message);
  } finally {
    busy = false;
    updateControls();
  }
}

function rememberInUrl(a, b, data, sims) {
  const params = new URLSearchParams({ a, b, seed: String(data.seed) });
  if (sims) params.set("sims", "1");
  history.replaceState(null, "", `?${params.toString()}`);
}

function showError(message) {
  setStatus(message, true);
}

/* ---------- rendering ---------- */

function render(data) {
  result.innerHTML = data.kind === "sims" ? renderSims(data) : renderGame(data);
  const heading = result.querySelector("h2");
  if (heading) {
    heading.setAttribute("tabindex", "-1");
    heading.focus({ preventScroll: true });
  }
  result.scrollIntoView({ block: "start", behavior: reducedMotion() ? "auto" : "smooth" });
}

function renderGame(game) {
  const [a, b] = game.teams;
  const winnerSide = game.winner === a.abbr ? "a" : game.winner === b.abbr ? "b" : "tie";
  const tag = game.winner === null ? "Tie after overtime" : game.ot ? "Final, overtime" : "Final";

  return `
    <section aria-labelledby="final-heading">
      <h2 id="final-heading" class="visually-hidden">${escapeHtml(tag)}: ${escapeHtml(a.name)} ${a.points}, ${escapeHtml(b.name)} ${b.points}</h2>
      <p class="final-tag" aria-hidden="true">${escapeHtml(tag)}</p>
      <div class="scoreboard" aria-hidden="true">
        <div class="side a ${winnerSide === "b" ? "loser" : ""}">
          <span class="team-name">${escapeHtml(a.name)}</span>
          <span class="score">${a.points}</span>
        </div>
        <div class="side b ${winnerSide === "a" ? "loser" : ""}">
          <span class="team-name">${escapeHtml(b.name)}</span>
          <span class="score">${b.points}</span>
        </div>
      </div>
      <div class="field-track" aria-hidden="true"><div class="marker win-${winnerSide === "tie" ? "tie tie" : winnerSide}"></div></div>
      <p class="seed-note">Seed ${game.seed}. Enter it under Options to replay this exact game, or copy the page address, which remembers it.</p>
    </section>

    <section class="block" aria-labelledby="line-heading">
      <h2 id="line-heading">Score by quarter</h2>
      ${lineScore(game)}
    </section>

    <section class="block" aria-labelledby="team-heading">
      <h2 id="team-heading">Team stats</h2>
      ${teamStats(game)}
    </section>

    <section class="block" aria-labelledby="player-heading">
      <h2 id="player-heading">Player stats</h2>
      <div class="players">
        ${playerColumn(a, "a")}
        ${playerColumn(b, "b")}
      </div>
    </section>

    ${game.log.length ? playByPlay(game.log) : ""}
  `;
}

function lineScore(game) {
  const quarters = game.teams[0].quarters.length;
  const head = Array.from({ length: quarters }, (_, i) => (i === 4 ? "OT" : String(i + 1)));
  const rows = game.teams
    .map(
      (t) => `
      <tr>
        <th scope="row">${escapeHtml(t.name)}</th>
        ${t.quarters.map((q) => `<td>${q}</td>`).join("")}
        <td class="total">${t.points}</td>
      </tr>`
    )
    .join("");
  return `
    <div class="table-scroll line-score">
      <table>
        <caption class="visually-hidden">Points by quarter</caption>
        <thead><tr><th scope="col">Team</th>${head.map((h) => `<th scope="col">${h}</th>`).join("")}<th scope="col" class="total">Final</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>`;
}

function teamStats(game) {
  const [a, b] = game.teams;
  const rows = [
    ["Total yards", "total_yds"],
    ["Passing yards (net of sacks)", "pass_yds"],
    ["Rushing yards", "rush_yds"],
    ["Plays", "plays"],
    ["Yards per play", "yards_per_play", 1],
    ["First downs", "first_downs"],
    ["Turnovers", "turnovers"],
    ["Sacks by the defense", "sacks"],
  ];
  const body = rows
    .map(([label, key, digits = 0]) => {
      const x = a.stats[key];
      const y = b.stats[key];
      const total = x + y;
      const share = total > 0 ? (100 * x) / total : 50;
      return `
        <div class="stat">
          <div class="label">${label}</div>
          <span class="val a">${number(x, digits)}</span>
          <div class="track" aria-hidden="true"><div class="bar a" style="--w:${share.toFixed(1)}%"></div><div class="bar b"></div></div>
          <span class="val b">${number(y, digits)}</span>
        </div>`;
    })
    .join("");
  return `
    <div class="legend"><span class="a">${escapeHtml(a.name)}</span><span class="b">${escapeHtml(b.name)}</span></div>
    <div class="stats">${body}</div>`;
}

function playerTable(caption, columns, rows) {
  if (!rows.length) return "";
  const head = columns.map((c) => `<th scope="col">${c}</th>`).join("");
  const body = rows
    .map(([name, ...cells]) => `<tr><th scope="row">${escapeHtml(name)}</th>${cells.map((c) => `<td>${escapeHtml(c)}</td>`).join("")}</tr>`)
    .join("");
  return `
    <div class="table-scroll">
      <table>
        <caption>${caption}</caption>
        <thead><tr><th scope="col">Player</th>${head}</tr></thead>
        <tbody>${body}</tbody>
      </table>
    </div>`;
}

function playerColumn(team, side) {
  const p = team.players;
  const passing = playerTable(
    "Passing",
    ["Comp/Att", "Yards", "TD", "INT", "Sacked"],
    p.passing.map((x) => [x.name, `${x.comp}/${x.att}`, x.yds, x.td, x.int, x.sacked])
  );
  const rushing = playerTable(
    "Rushing",
    ["Carries", "Yards", "Avg", "TD", "Fumbles"],
    p.rushing.map((x) => [x.name, x.att, x.yds, (x.yds / x.att).toFixed(1), x.td, x.fum])
  );
  const receiving = playerTable(
    "Receiving",
    ["Targets", "Catches", "Yards", "TD"],
    p.receiving.map((x) => [x.name, x.tgt, x.rec, x.yds, x.td])
  );
  const kicking = playerTable(
    "Kicking",
    ["Field goals", "Longest", "Extra points"],
    p.kicking.map((x) => [x.name, `${x.fg_made}/${x.fg_att}`, x.fg_long || "none", `${x.xp_made}/${x.xp_att}`])
  );
  const fantasy = playerTable(
    "Fantasy points (PPR)",
    ["Points"],
    p.fantasy.map((x) => [x.name, x.pts.toFixed(1)])
  );
  return `<div class="team-col ${side}"><h3>${escapeHtml(team.name)}</h3>${fantasy}${passing}${rushing}${receiving}${kicking}</div>`;
}

function playByPlay(log) {
  const items = log
    .map((line) => {
      const split = line.indexOf(" - ");
      if (split === -1 || line.startsWith("---")) return `<li class="note">${escapeHtml(line)}</li>`;
      const situation = line.slice(0, split);
      const text = line.slice(split + 3);
      const scoring = /TOUCHDOWN|field goal is good/.test(text);
      return `<li class="${scoring ? "scoring" : ""}"><span class="situation">${escapeHtml(situation)}</span><span>${escapeHtml(text)}</span></li>`;
    })
    .join("");
  const plays = log.filter((l) => l.includes(" - ") && !l.startsWith("---")).length;
  return `
    <section class="block pbp" aria-labelledby="pbp-heading">
      <h2 id="pbp-heading">Play by play</h2>
      <details>
        <summary>Show all ${plays} plays</summary>
        <ol>${items}</ol>
      </details>
    </section>`;
}

function renderSims(data) {
  const [a, b] = data.teams;
  const tiePct = (100 * data.ties) / data.n;
  const leader = a.win_pct === b.win_pct ? null : a.win_pct > b.win_pct ? a : b;
  const caption = leader
    ? `${escapeHtml(leader.name)} won more often. The yellow line marks an even split.`
    : "The two teams won equally often. The yellow line marks an even split.";

  const scores = data.common_scores
    .map((c) => `<li>${escapeHtml(a.abbr)} ${c.score[0]}, ${escapeHtml(b.abbr)} ${c.score[1]} (${c.count} ${c.count === 1 ? "game" : "games"})</li>`)
    .join("");

  const rows = data.teams
    .map(
      (t) => `
      <tr>
        <th scope="row">${escapeHtml(t.name)}</th>
        <td class="total">${number(t.win_pct, 1)}%</td>
        <td>${number(t.avg_points, 1)}</td>
        <td>${number(t.avg_pass_yds)}</td>
        <td>${number(t.avg_rush_yds)}</td>
      </tr>`
    )
    .join("");

  return `
    <section aria-labelledby="sims-heading">
      <h2 id="sims-heading" class="sims-title">${number(data.n)} games: ${escapeHtml(a.name)} vs ${escapeHtml(b.name)}</h2>
      <div class="odds" role="img" aria-label="${escapeHtml(a.name)} won ${number(a.win_pct, 1)} percent, ${escapeHtml(b.name)} won ${number(b.win_pct, 1)} percent, ties ${number(tiePct, 1)} percent">
        <div class="a" style="width:${a.win_pct}%"><span>${number(a.win_pct, 1)}%</span></div>
        <div class="tie" style="width:${tiePct}%"></div>
        <div class="b" style="width:${b.win_pct}%"><span>${number(b.win_pct, 1)}%</span></div>
        <div class="mid"></div>
      </div>
      <p class="odds-caption">${caption}${data.ties ? ` Ties (${number(tiePct, 1)}%) count as neither win.` : ""}</p>
      <p class="seed-note">Games used seeds ${data.seed} to ${data.seed + data.n - 1}.</p>
    </section>

    <section class="block" aria-labelledby="avg-heading">
      <h2 id="avg-heading">Averages per game</h2>
      <div class="table-scroll">
        <table>
          <caption class="visually-hidden">Win percentage and average points and yards for each team</caption>
          <thead><tr><th scope="col">Team</th><th scope="col">Wins</th><th scope="col">Points</th><th scope="col">Passing yards</th><th scope="col">Rushing yards</th></tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
    </section>

    <section class="block" aria-labelledby="fantasy-heading">
      <h2 id="fantasy-heading">Average fantasy points per game (PPR)</h2>
      <div class="players">
        ${data.teams
          .map(
            (t, i) =>
              `<div class="team-col ${i === 0 ? "a" : "b"}"><h3>${escapeHtml(t.name)}</h3>${playerTable(
                "Average fantasy points",
                ["Avg points"],
                t.avg_fantasy.map((x) => [x.name, x.pts.toFixed(1)])
              )}</div>`
          )
          .join("")}
      </div>
    </section>

    <section class="block" aria-labelledby="common-heading">
      <h2 id="common-heading">Most common final scores</h2>
      <ol class="common">${scores}</ol>
    </section>`;
}

/* ---------- events ---------- */

$("#controls").addEventListener("submit", (event) => {
  event.preventDefault();
  play(0);
});
playMany.addEventListener("click", () => play(SIM_GAMES));
randomButton.addEventListener("click", () => {
  randomMatchup();
  setStatus(engineReady ? "Ready." : statusLine.textContent);
});

loadTeams();
