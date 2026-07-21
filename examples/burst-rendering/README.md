# Rendering a one-burst reply

Chat UIs grew up around models that trickle tokens, so the standard kit is
streaming text, blinking cursors, and progress spinners. celeris-1 delivers
the whole reply at once, typically in about 300 ms, and that kit becomes the
wrong mental model: there is nothing to trickle, and a token-by-token
animation would slow down text that already arrived.

This example is a small React component with three treatments for a reply
that lands whole, plus a demo page that simulates a 300 ms model call and
renders all three side by side.

## Run it

```sh
cd examples/burst-rendering
npm install
npm run dev
# open the printed local URL and press "Deliver reply"
```

No credentials needed: the demo simulates the arrival timing so the
rendering itself is the subject. Wire it to a real call with the
[chatbot example](../chatbot)'s server.

## The three treatments

| Mode | What it does | When it feels best |
| --- | --- | --- |
| `instant` | Full reply the moment it lands. | The honest default. Best for tools, dashboards, and anything users read repeatedly. |
| `fade` | One 180 ms opacity and translate transition. | When an abrupt swap feels jarring, such as replacing prior content. |
| `typewriter` | Characters revealed over a **fixed** 300 ms, regardless of length. | Consumer chat surfaces where users expect text to "arrive". |

Rules the component enforces, and your UI should too:

- **Never scale animation time by reply length.** A long reply must not
  read slower than a short one; the fixed-duration typewriter caps the cost
  of the effect at about one perceptible beat.
- **Compute reveal position from elapsed time, not accumulation**, and
  drive it with an interval rather than only requestAnimationFrame, so
  throttled or backgrounded tabs still complete the reveal on schedule.
- **Respect `prefers-reduced-motion`.** All modes collapse to `instant`.
- **No spinners between tokens.** The only waiting state is the ~300 ms
  before the burst; show one quiet "working" hint for that window and then
  the whole answer. See the [latency guide](../../guides/latency.md) for
  why TTFT equals total on this model.

## How it works

`BurstReply.tsx` is self-contained (about 80 lines): a `mode` prop, a
reduced-motion hook, and one effect per treatment. The demo page
(`App.tsx`) simulates the model call with a 300 ms timer so you can replay
the arrival as many times as you like.
