// SillyTavern server plugin: start local_search.py with SillyTavern, stop it with SillyTavern.
//
// Install once (junction, so edits in the repo take effect with no copy step):
//   mklink /J "<SillyTavern>\plugins\local-search" "<this repo>\st-plugin"
// Requires enableServerPlugins: true in SillyTavern's config.yaml.
// Extra local_search.py options go in LOCAL_SEARCH_ARGS, e.g. LOCAL_SEARCH_ARGS="--safesearch off --region uk-en".

import { spawn, spawnSync } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const PORT = Number(process.env.LOCAL_SEARCH_PORT) || 18888;
const HOST = process.env.LOCAL_SEARCH_HOST || '127.0.0.1';
const EXTRA_ARGS = (process.env.LOCAL_SEARCH_ARGS || '').split(/s+/).filter(Boolean);
// ../local_search.py — import.meta resolves through the junction to the real repo path.
const SCRIPT = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'local_search.py');

/** @type {import('node:child_process').ChildProcess | null} */
let child = null;

export const info = {
    id: 'local-search',
    name: 'Local Search',
    description: 'Runs the keyless DuckDuckGo-backed search endpoint for the Web Search extension.',
};

/** Is something already serving on the port? (e.g. Start-LocalSearch.bat is open) */
async function alreadyRunning() {
    try {
        const ac = AbortSignal.timeout(1500);
        await fetch(`http://${HOST}:${PORT}/`, { signal: ac });
        return true;
    } catch {
        return false;
    }
}

/** Real path of the first interpreter that can import ddgs, or null. Spawning it directly
 *  (not through the py launcher) means exit() kills the process that owns the port. */
function findPython() {
    for (const [cmd, pre] of [['py', ['-3']], ['python', []], ['python3', []]]) {
        const probe = spawnSync(cmd, [...pre, '-c', 'import ddgs, sys; print(sys.executable)'], { windowsHide: true, timeout: 20000, encoding: 'utf8' });
        const exe = probe.status === 0 ? probe.stdout.trim() : '';
        if (exe) return exe;
    }
    return null;
}

export async function init() {
    if (await alreadyRunning()) {
        console.log(`[local-search] already serving on ${HOST}:${PORT}, not starting a second one`);
        return;
    }

    const python = findPython();
    if (!python) {
        console.error('[local-search] no Python with the "ddgs" package found. Run: py -3 -m pip install -U ddgs');
        return;
    }

    child = spawn(python, [SCRIPT, '--host', HOST, '--port', String(PORT), ...EXTRA_ARGS], {
        cwd: path.dirname(SCRIPT),
        windowsHide: true,
        stdio: ['ignore', 'ignore', 'pipe'],
    });
    // local_search.py logs everything to stderr; surface failures instead of swallowing them.
    child.stderr?.on('data', (d) => process.stderr.write(`[local-search] ${d}`));
    child.on('exit', (code, signal) => {
        console.log(`[local-search] exited (code=${code}, signal=${signal})`);
        child = null;
    });
    console.log(`[local-search] started on http://${HOST}:${PORT} (pid ${child.pid})`);
}

export async function exit() {
    if (!child) return;
    const pid = child.pid;
    child.kill();
    child = null;
    console.log(`[local-search] stopped (pid ${pid})`);
}

export default { info, init, exit };
