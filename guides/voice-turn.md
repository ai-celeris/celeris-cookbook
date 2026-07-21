# The voice turn budget

A voice agent answers a turn in three model steps: speech to text, the
language model reply, and text to speech. Users judge the whole gap. In
human conversation the median gap between turns is about 200 ms
(Stivers et al., PNAS 2009, "Universals and cultural variation in
turn-taking in conversation"), and anything much past a second feels like
talking to a machine. The language model step is usually the budget's
biggest line item, and it is the one you can change most easily.

This guide has one measured component (the celeris-1 reply step) and cites
the rest. It uses no speech dependencies; it is a budget, not a voice app.

## Measured: the reply step on celeris-1

Ten realistic voice turns (timers, lookups, small talk, a translation),
`max_tokens` 256, one to two sentence replies, run live on 2026-07-22:

```text
p50 288 ms, mean 363 ms, min 270 ms, max 1020 ms (n=10)
```

The 1020 ms outlier was the first request on a cold connection; the nine
warm turns sat between 270 and 322 ms. Reply quality was appropriate for a
voice surface: short, direct, and honest about missing tool access. Because
celeris-1 delivers the whole reply as one burst (see the
[latency guide](latency.md)), text to speech can start on the complete
sentence immediately; there is no token trickle to wait out.

## Cited: the speech steps

These numbers are vendor-published or commonly advertised figures, not our
measurements, and your stack will vary:

- **Speech to text (streaming)**: major streaming APIs advertise
  finalization on the order of 300 ms after end of speech (for example
  Deepgram, deepgram.com, and AssemblyAI, assemblyai.com, both advertise
  roughly 300 ms streaming latency). Budget 150 to 400 ms.
- **Text to speech (time to first audio)**: low-latency TTS vendors
  advertise well under 200 ms to first audio (for example ElevenLabs Flash,
  elevenlabs.io, advertises about 75 ms model time; Cartesia, cartesia.ai,
  advertises under 100 ms). With network overhead, budget 100 to 300 ms.
- **A large hosted LLM** for a short conversational reply commonly takes 1
  to 1.5 seconds end to end. This is the line the fast model rewrites.

## The budget, both ways

| step | typical with a large LLM | with celeris-1 (measured) |
| --- | --- | --- |
| Speech to text finalization (cited) | 150 to 400 ms | 150 to 400 ms |
| LLM reply | 1000 to 1500 ms (cited) | **288 ms p50 (measured)** |
| Text to speech first audio (cited) | 100 to 300 ms | 100 to 300 ms |
| **Total turn gap** | **1.25 to 2.2 s** | **0.54 to 1.0 s** |

The speech steps are identical in both columns. Swapping the reply step
moves the whole turn from "noticeable pause" into the range where the agent
answers about as fast as a person.

## Which turns suit which model

Most voice turns are exactly the shapes a fast model handles well:
confirmations, device commands, list edits, timers, short factual answers,
and routing to tools. Keep those on celeris-1 and the conversation stays
conversational.

For the occasional genuinely hard turn (multi-step planning, long
reasoning), use the [cascade pattern](cascade.md): answer immediately with
the fast model ("let me work that out") or route the turn to a larger model
and spend the seconds only where they buy something. If you are unsure
which of your turns fit, run them through the
[task-fit harness](../examples/task-fit); it will tell you per turn.
