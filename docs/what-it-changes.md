# What the installer changes

[Back to the README](../README.md)

## What these modifications actually do

Five changes. Each one exists because something silently misbehaves without it.

### 1. `plugins/local-search` — a SillyTavern server plugin

A junction from SillyTavern's `plugins` folder to this repo's `st-plugin/`.

SillyTavern loads it at boot, and the plugin spawns `local_search.py`. That
process is the search backend: it answers on `127.0.0.1:18888` in the HTML
shape SillyTavern's Web Search extension already knows how to read, backed by
DuckDuckGo.

**Effect:** search starts and stops with SillyTavern. No window to remember, no
process left running afterwards.

It checks the port first, so running `Start-LocalSearch.bat` by hand still
works — the plugin sees the endpoint is already up and leaves it alone. If no
Python on `PATH` can `import ddgs`, it says so in the console and starts
nothing, rather than failing at your first search.

A junction rather than a copy, so `git pull` on this repo updates the plugin
with no second step.

**To undo:** delete `<SillyTavern>/plugins/local-search`.

### 2. `enableServerPlugins: true` in `config.yaml`

Required for the above. SillyTavern refuses to load any server plugin without
it, silently.

**To undo:** set it back to `false`.

### 3. Web Search → the local endpoint

Source `searxng`, URL `http://127.0.0.1:18888`. The extension's SearXNG client
is the only keyless one it has, and `local_search.py` speaks that shape, so no
account and no API key are involved anywhere.

**Effect:** the model can look things up, for free, without a SerpApi or Tavily
key.

### 4. Trigger phrases **off**, backticks **on**

This is the one that changes how it feels to use.

The extension ships 52 trigger phrases, and they are not search-shaped:
`can you`, `tell me`, `what is`, `who is`, `why do`, `how does`, `find me`.
Ordinary in-character dialogue hits those constantly, and every hit is a live
DuckDuckGo round trip plus an injected block of search results at depth 2 — on
a turn where nobody asked for the web.

**Effect:** search fires when you write `` `current version of rust` `` and at
no other time. Roleplay turns go back to being roleplay turns.

**To undo:** Extensions → Web Search → re-tick *Use trigger phrases*.

### 5. Prompt Post-Processing → `semi_tools`

Only set if you are already on Custom (OpenAI-compatible), because this field
is sent to *every* source and forcing it would change a hosted API's prompt too.

Strict chat templates — Qwen3 and its many fine-tunes — allow a `system`
message only as the very first message. SillyTavern sends them mid-conversation
constantly: the jailbreak block, author's note, world info at depth, and the
search results from change 4. The model then rejects the whole request:

```
Jinja Exception: System message must be at the beginning.
```

which surfaces in SillyTavern as a bare `Bad Request` and reads like a broken
connection.

`semi_tools` runs SillyTavern's own `mergeMessages`, which rewrites mid-prompt
`system` messages as `user` messages and merges neighbours. The `_tools` suffix
matters: plain `semi` fixes the crash and *silently disables function calling*,
because `isToolCallingSupported()` only sends tool definitions for `none`,
`merge_tools`, `semi_tools` and `strict_tools`.

**Effect:** the model answers instead of erroring, and keeps its tools.

**Careful:** this value is also stored in every Chat Completion **preset**.
Loading a preset overwrites the live setting, so a preset saved before this fix
will bring the crash back with nothing to point at. See
[The preset silently puts the crash back](lm-studio.md#the-preset-silently-puts-the-crash-back).

### What is not touched

Your presets, characters, chats, lorebooks, personas, themes and other
extensions. `settings.json` is backed up to `settings.json.bak-install` before
the first write.

## Why a SillyTavern update cannot remove them

**A SillyTavern update cannot remove these tweaks.** Everything touched here is
in SillyTavern's own `.gitignore`:

```
/config.yaml
/plugins/
/data
public/scripts/extensions/third-party/
```

so `git pull` never sees any of it. The re-run is belt and braces.

Only `Extension-WebSearch` gets updated. Any other extension in `third-party/`
— including your own — is left alone, and the Web Search extension itself is
skipped if it has local changes.
