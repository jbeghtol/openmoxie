# Choosing a chat model

GPT-6 Luna is an optional, lower-cost alternative to the default GPT-3.5 Turbo
chat model. This support applies to conversation replies and summaries.
It does not change speech recognition, robot firmware or built-in activities.

## Enable GPT-6 Luna

1. Back up your `local/work` directory and note the current model values.
2. In the Hive dashboard, open **Admin**, then **Single prompt chats**.
3. For **OpenMoxie Chat - Long** and **OpenMoxie Chat - Short**, set **Model**
   to `gpt-6-luna` and save. Keep the other fields unchanged.
4. Start a new chat session. An already-running session keeps its existing model;
   switching activities and returning to chat creates a new session. No database
   migration or firmware change is required.

Your API project must have access to the selected model. To revert, restore the
previous model values and start a new session. This change does not automatically
modify existing database records or factory defaults.

Luna requires `max_completion_tokens` rather than `max_tokens`. OpenMoxie sets
`reasoning_effort="none"` for its short conversational replies and omits the
legacy temperature parameter. Other configured models retain their existing
request parameters. The configured token limit remains in effect.

## Chat token rates

Standard, uncached text-token prices checked on 16 October 2026, in USD per
million tokens:

| Model | Input | Output |
| --- | ---: | ---: |
| [GPT-3.5 Turbo](https://developers.openai.com/api/docs/models/gpt-3.5-turbo) | $0.50 | $1.50 |
| [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna) | $0.10 | $0.50 |

At equal token counts, Luna's input rate is **80% lower** and its output rate is
**66.7% lower**. For example, one million input tokens plus one million output
tokens would cost $0.60 instead of $2.00, a **70% reduction in chat-token cost**.

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

The tests exercise both conversation and summary requests, legacy compatibility,
model overrides and the existing API-error fallback. API calls are mocked.
