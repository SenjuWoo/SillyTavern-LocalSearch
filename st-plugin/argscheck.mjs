// Offline check for how the plugin reads LOCAL_SEARCH_ARGS. No network, no Python.
// Run:  node st-plugin/argscheck.mjs
import assert from 'node:assert/strict';
import { splitArgs } from './index.mjs';

assert.equal(typeof splitArgs, 'function', 'index.mjs must export splitArgs');
// The README example. 1.1.0 split on the letter "s" and turned this into ["--", "afe", "earch off --region uk-en"].
assert.deepEqual(splitArgs('--safesearch off --region uk-en'), ['--safesearch', 'off', '--region', 'uk-en']);
assert.deepEqual(splitArgs('  --timelimit w\t--backend  brave,wikipedia\n'), ['--timelimit', 'w', '--backend', 'brave,wikipedia']);
assert.deepEqual(splitArgs('--verbose'), ['--verbose']);
assert.deepEqual(splitArgs(''), []);
assert.deepEqual(splitArgs(undefined), []);

console.log('ok - LOCAL_SEARCH_ARGS splits on whitespace');
