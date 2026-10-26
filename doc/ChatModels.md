# Choosing a chat model

OpenMoxie defaults to [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna)
for conversation replies and summaries. Luna is a lower-cost, low-latency option
suited to short spoken replies. Speech recognition, robot firmware, and built-in
activities are unchanged.

Factory stock chats (`OPENMOXIE_CHAT`, `OPENCONVO`, and newly created
Single Prompt chats) use `gpt-6-luna`. After upgrading OpenMoxie, `init_data`
updates those stock records when their `source_version` increases. Custom chats
you created yourself are left alone.

## Request parameters

OpenMoxie maps each configured model to Chat Completions parameters:

| Model family | Token limit | Sampling / reasoning |
| --- | --- | --- |
| Legacy chat (e.g. `gpt-4o-mini`) | `max_tokens` | `temperature` |
| Reasoning models that accept `none` (e.g. `gpt-6-luna`, most GPT-5/6) | `max_completion_tokens` | `reasoning_effort="none"` and `temperature` |
| Other reasoning models (e.g. o-series, GPT-6 Astra) | `max_completion_tokens` | `reasoning_effort="low"` (no `temperature`) |

That keeps short conversational replies fast on Luna while still allowing other
OpenAI models in Admin. Your API project must have access to any model you select.

## Changing or rolling back a model

1. Back up your `local/work` directory if you want an easy restore point.
2. In the Hive dashboard, open **Admin**, then **Single prompt chats**.
3. Set **Model** to the OpenAI model id you want (for example `gpt-6-luna` or
   another chat-capable model) and save.
4. Start a new chat session. An already-running session keeps its existing model;
   switching activities and returning to chat creates a new session.

No firmware change is required. Stock defaults only change again when a future
OpenMoxie release bumps `source_version` in `site/data/default_conversations.json`.

## Chat token rates

Standard, uncached text-token prices checked on 16 October 2026, in USD per
million tokens:

| Model | Input | Output |
| --- | ---: | ---: |
| [GPT-3.5 Turbo](https://developers.openai.com/api/docs/models/gpt-3.5-turbo) (deprecated) | $0.50 | $1.50 |
| [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna) | $0.10 | $0.50 |

At equal token counts, Luna's input rate is **80% lower** and its output rate is
**66.7% lower** than the old GPT-3.5 Turbo rates. For example, one million input
tokens plus one million output tokens would cost $0.60 instead of $2.00.

These are rate comparisons, not measured reductions in a complete OpenMoxie
bill. Token counts, conversation history and usage can differ between models;
speech-transcription charges are unchanged. Check the linked prices before
estimating your own costs.

Changing the model does not enable live news or web browsing. Those require a
separate retrieval integration.

## Offline checks

From the `site` directory, run:

```sh
python -m unittest hive.test_chat_models -v
```

The tests exercise reasoning and legacy request paths, summary model overrides,
and the existing API-error fallback. API calls are mocked.
