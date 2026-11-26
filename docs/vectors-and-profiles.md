# Vectors and Connection Profiles

[Back to the README](../README.md)

## 4. Local RAG on the same endpoint (Vectors)

If LM Studio also serves an embedding model, the **Vectors** extension gets you
retrieval over your chats and files with no second service and no key.

**Check `lms ps` against `nvidia-smi` first.** This is a second model competing
for the same card; see [What this costs at run time](runtime-costs.md#vectors-needs-vram-you-may-not-have) for what happens when it does not fit.

There is no "custom OpenAI-compatible" option in the Vectorization Source
dropdown, which makes it look unsupported. Use **vLLM** — [`src/vectors/vllm-vectors.js`](https://github.com/SillyTavern/SillyTavern/blob/release/src/vectors/vllm-vectors.js)
POSTs plain `{ input, model }` to `<url>/v1/embeddings`, which is exactly what
LM Studio serves:

| Field | Value |
|---|---|
| Vectorization Source | **vLLM** |
| Use alternative endpoint | **on** |
| Alt endpoint URL | `http://127.0.0.1:1234/v1` |
| Model | `text-embedding-nomic-embed-text-v1.5` |

The alt-endpoint toggle matters: without it the extension reads the vLLM server
URL out of the Text Completion settings instead, and `validateSettings()`
throws `Vectors: API URL missing` before any request goes out.

No API key is needed. `setAdditionalHeadersByType` sends no `Authorization`
header when the vLLM secret is unset, and LM Studio does not check one.

Measured through SillyTavern's own `/api/vector/insert` and `/api/vector/query`,
three unrelated sentences indexed, then queried with wording that shares no
words with any of them:

```
query: "what weapon does she hide"
  1. "Seraphina keeps a silver dagger under her pillow."
  2. "Rust 1.90 was current at the time of writing."
  3. "The tavern in Riverwood serves mead brewed with juniper."
```

768 dimensions, batches of 5, entirely on the same GPU already holding the chat
model.

---

## 5. One click per backend (Connection Profiles)

Switching between a local model and a hosted one means changing the source, the
URL, the model, the preset and the post-processing dropdown, in that order,
every time. **Connection Profiles** (in the API panel) collapse that into one
select.

A profile is stored in `extension_settings.connectionManager.profiles`:

```json
{
    "id": "<uuid>",
    "mode": "cc",
    "name": "LM Studio (local)",
    "api": "custom",
    "preset": "<your preset> (LM Studio)",
    "api-url": "http://127.0.0.1:1234/v1",
    "model": "qwen3.6-35b-a3b-uncensored-genesis-hermes-v10",
    "prompt-post-processing": "semi_tools",
    "exclude": []
}
```

`api` takes a key from `CONNECT_API_MAP` — `custom` for Custom
(OpenAI-compatible), `openrouter` for OpenRouter, and so on. Applying a profile
replays those fields as slash commands in a fixed order and skips any that are
empty, so a partial profile is fine.

Because the profile sets **both** the preset and the post-processing, it is also
the durable answer to the trap above: pick the profile and the pair can no
longer drift apart.
