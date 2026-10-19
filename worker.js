/* Runs the Python game engine (footballsim.py) in the browser using Pyodide.
   It lives in a worker so the page stays responsive while Python loads and
   while 1,000 games are played. */

// Pinned to one release of Pyodide's official build on jsDelivr. (The npm copy
// of 314.0.7 was rejected by importScripts in a real browser, so do not switch
// back without testing in one.)
const PYODIDE_VERSION = "0.28.3";
const PYODIDE_BASE = `https://cdn.jsdelivr.net/pyodide/v${PYODIDE_VERSION}/full/`;

// Thin wrapper around footballsim.run_for_web. Errors come back as JSON so the
// page can show them in plain words.
const PY_SHIM = `
import json
import footballsim as fs

TEAMS = fs.load_teams("nfl_teams.json")

def go(a, b, seed, pbp, sims):
    try:
        text = str(seed).strip()
        seed = int(text) if text else None
        return fs.run_for_web(TEAMS, a, b, seed, bool(pbp), int(sims))
    except ValueError as e:
        message = "The seed must be a whole number." if "invalid literal" in str(e) else str(e)
        return json.dumps({"kind": "error", "message": message})
`;

async function fetchText(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Could not load ${url} (${response.status})`);
  return response.text();
}

let go = null;

const ready = (async () => {
  postMessage({ type: "status", text: "Loading Python (about 10 MB the first time)…" });
  try {
    importScripts(PYODIDE_BASE + "pyodide.js");
  } catch (err) {
    throw new Error(`could not download Pyodide from ${PYODIDE_BASE} (${(err && err.message) || err})`);
  }
  const pyodide = await loadPyodide({ indexURL: PYODIDE_BASE });

  postMessage({ type: "status", text: "Loading the game engine…" });
  const [engine, teams] = await Promise.all([fetchText("footballsim.py"), fetchText("nfl_teams.json")]);
  pyodide.FS.writeFile("footballsim.py", engine);
  pyodide.FS.writeFile("nfl_teams.json", teams);
  await pyodide.runPythonAsync(PY_SHIM);
  go = pyodide.globals.get("go");
  postMessage({ type: "ready" });
})().catch((err) => {
  postMessage({ type: "fatal", message: String((err && err.message) || err) });
});

self.onmessage = async (event) => {
  const { id, a, b, seed, pbp, sims } = event.data;
  await ready;
  if (!go) {
    postMessage({ id, error: "The simulator did not finish loading. Reload the page and try again." });
    return;
  }
  try {
    postMessage({ id, result: JSON.parse(go(a, b, seed, pbp, sims)) });
  } catch (err) {
    postMessage({ id, error: String((err && err.message) || err) });
  }
};
