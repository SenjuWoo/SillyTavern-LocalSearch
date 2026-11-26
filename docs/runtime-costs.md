# What this costs at run time

[Back to the README](../README.md)

Three settings look free and are not. All three were measured on a 16 GB card
running a model whose weights are 16.24 GB, which is the interesting case.

## Web search fires on almost every roleplay turn

The extension ships **52 trigger phrases**, and they are not "search-shaped":

```
can you · tell me · what is · what are · who is · why do · why is
how to · how does · how do you · where is · when did · find me · explain me
```

Ordinary in-character dialogue hits those constantly. Every hit is a live
DuckDuckGo round trip plus an injected block at depth 2, on a turn where nobody
asked for the web.

Turn **trigger phrases off** and leave **backticks on**. Search then happens
when you write `` `current rust version` `` and at no other time, which is what
"search when I ask" actually means.

## Vectors needs VRAM you may not have

Embeddings are a *second model*. If the chat model already fills the card,
every embed call evicts it, and the next turn reloads 16 GB from disk:

```
00:27:27  POST /v1/embeddings                        <- Vectors, on a normal turn
00:27:28  ERROR ... Model is unloaded.               <- chat model evicted
00:27:29  [LlamaEmbeddingEngine] Model load complete!
00:27:33  POST /v1/chat/completions                  <- reloading 16 GB to answer
```

`lms ps` tells you before you start:

```
qwen3.6-35b-...   18.34 GB   65536      <- footprint
nvidia-smi        15454 MiB used, 592 MiB free of 16376 MiB
```

18.34 GB of model against 592 MiB of headroom. There is no room for an 84 MB
embedder, or for anything else. Vectors is worth having when the numbers leave
room for it and is actively harmful when they do not.

## Reasoning tokens are the latency, and the API cannot turn them off

A reasoning model spends the reply budget thinking first. Measured on this one,
asking for a single sentence:

| Request | completion tokens | of which reasoning | visible text |
|---|---|---|---|
| baseline | 362 | 331 | one sentence |
| `reasoning_effort: low` | 363 | 330 | one sentence |
| `/no_think` in the message | 778 | 747 | one sentence |
| `/nothink` in the message | 490 | 456 | one sentence |
| `chat_template_kwargs: {enable_thinking: false}` | — | — | `{"error":"terminated"}` |

None of the usual switches work. `reasoning_effort` is accepted and ignored,
the Qwen `/no_think` soft switches make it *think harder*, and
`chat_template_kwargs` is rejected outright. A real roleplay turn on this setup
decoded 3,318 tokens at 52 tok/s — about a minute of thinking before the first
visible word.

The only working control is on the server side: LM Studio's
`llm.prediction.reasoning.budgetTokens`, set in the model's config in the
Developer tab. It is not reachable through the OpenAI-compatible API, so no
SillyTavern setting can substitute for it.

## JIT loading picks its own context length

Letting SillyTavern's first request load the model is convenient and quietly
wrong. LM Studio sizes a just-in-time load to the request it is answering:

```
lms ps
qwen3.6-35b-...   IDLE   18.34 GB   5888        <- after a short first message
```

5,888 tokens. The first long roleplay prompt then does not fit and the model is
reloaded — 16 GB off disk, mid-conversation. Load it yourself instead, once:

```bash
lms load <model-key> -c 65536 --ttl 86400
```

`--ttl` is what stops it being unloaded again between sessions; the default is
an hour.

## The weights have to fit, and context length will not save you

`lms load --estimate-only` reports the same **17.08 GiB** at 65,536, 32,768 and
16,384 context, because the KV cache is not what is over budget — the weights
are:

```
Hermes3.6-35B-A3B-...-APEX-Compact.gguf    16.24 GB
RTX 4080 SUPER                             15.99 GB usable
```

Shrinking context does not make a 16.24 GB model fit a 15.99 GB card. Only a
smaller quantisation does. Generation still runs at ~52 tok/s because an
A3B mixture-of-experts activates about 3B parameters per token, so the spill
hurts prompt processing far more than it hurts streaming.
