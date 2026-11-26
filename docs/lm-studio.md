# LM Studio as a SillyTavern API

[Back to the README](../README.md)

Use **Chat Completion → Custom (OpenAI-compatible)**:

| Field | Value |
|---|---|
| Custom Endpoint | `http://127.0.0.1:1234/v1` |
| Custom API Key | any non-empty string |
| Model | picked from the dropdown once connected |

Start the server first — `lms server start`, or the toggle in the LM Studio
app. There is no CLI flag to auto-start it; check `lms server start --help` if
you expect one.

## The API key is required by SillyTavern, not by LM Studio

LM Studio ignores it completely. Verified both ways: `/v1/models` returns the
model list with a deliberately bogus bearer token **and** with no
`Authorization` header at all.

SillyTavern still refuses to enumerate models without one —
`src/endpoints/backends/chat-completions.js`:

```js
if (!apiKey && !request.body.reverse_proxy) {
    return statusResponse.status(400).send({ error: true });
}
```

The symptom is an empty model dropdown and a bare `{"error":true}`, which reads
like a connection problem and is not one. Put any word in the box.

## Reasoning models return nothing if the response length is small

This one costs an afternoon if you do not know it. With a reasoning model, the
thinking tokens come out of the **same budget** as the reply. Measured on a
Qwen3.6-35B-A3B build through SillyTavern:

| Response length | Result |
|---|---|
| 40 tokens | `''` — all 40 spent on reasoning, empty message |
| 600 tokens | the actual reply; 191 of 203 completion tokens were reasoning |

So a short Response Length does not give you a short answer, it gives you *no*
answer. Set it to 512 at the very minimum, and 1024+ in practice.

## Chat Completion connects, then every reply fails

Symptom: the model list loads, Text Completion works, and Chat Completion
returns nothing. LM Studio's log has:

```
Engine protocol predict request returned 500:
While executing CallExpression at line 85, column 32 in source:
...{{- raise_exception('System message must be at the beginning...
Error: Jinja Exception: System message must be at the beginning.
```

That is the *model's chat template* refusing the prompt, not a connection
problem. Qwen3-family templates allow `system` only as the first message.
SillyTavern sends `system` messages mid-conversation all the time — the
jailbreak block, author's note, world info at depth, and the Web Search
extension's own injection, which lands at depth 2 as a system message.

Fix it with **Prompt Post-Processing** in the Chat Completion panel, under the
connection fields. `mergeMessages` in `src/prompt-converters.js` does exactly
what the template wants:

```js
// Force mid-prompt system messages to be user messages
if (i > 0 && mergedMessages[i].role === 'system') {
    mergedMessages[i].role = 'user';
}
```

| Option | `custom_prompt_post_processing` | Note |
|---|---|---|
| None | `''` | the broken default here |
| Semi-strict, tools | `semi_tools` | **use this** |
| Strict, tools | `strict_tools` | also works; pads with a `Let's get started.` filler turn |
| Semi-strict / Strict | `semi` / `strict` | same merge, but silently disables tool calling |

The `_tools` variants matter: `isToolCallingSupported()` in
`public/scripts/tool-calling.js` only sends tool definitions when
post-processing is `none`, `merge_tools`, `semi_tools` or `strict_tools`.
Picking plain `semi` fixes the crash and quietly turns off function calling.

Measured against this setup, same five messages with a system message in the
middle, through SillyTavern's own `/api/backends/chat-completions/generate`:

| Post-processing | Result |
|---|---|
| `''` | `{"error":{"message":"Bad Request"}}` |
| `semi_tools` | `'The current Rust version is 1.90.'` |

## The preset silently puts the crash back

`custom_prompt_post_processing` lives in **two** places: `oai_settings` in
`settings.json`, and every Chat Completion **preset** file in
`data/<user>/OpenAI Settings/`. Loading a preset overwrites the live value.

So fixing the dropdown and then switching presets — or just reloading the one
you already had — restores `""` and the Jinja exception comes back, with no
obvious connection to what you changed. Fix it in the preset you actually use,
not only in the panel.

Presets carry `openai_max_context` too, which is the other half of the same
trap: a preset written for a hosted model can hold a context far larger than
anything you can load locally.

## Note for Hermes users

If you drive the same LM Studio model from
[Hermes](https://github.com/NousResearch/hermes-agent), **load it at 65,536
context or higher**. Hermes hard-refuses any model whose window is under 64,000
tokens and raises before the first turn. LM Studio commonly saves 32,768, which
is fine for SillyTavern and a non-starter there.
