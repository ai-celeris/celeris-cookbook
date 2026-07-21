import { useState } from "react";
import BurstReply, { type BurstMode } from "./BurstReply";

// Demo page: simulate a reply landing whole after ~300 ms (the shape of a
// real celeris-1 response), rendered three ways side by side.

const REPLY =
  "Your order shipped yesterday and is on track for delivery on Thursday. " +
  "You can still change the delivery address until the parcel reaches your " +
  "local depot. Refunds stay available for 30 days after delivery.";

const MODES: { mode: BurstMode; title: string; blurb: string }[] = [
  {
    mode: "instant",
    title: "Instant",
    blurb: "Show it the moment it lands. The honest default; fastest to read.",
  },
  {
    mode: "fade",
    title: "Fast fade",
    blurb: "One 180 ms transition. A sense of arrival, no meaningful delay.",
  },
  {
    mode: "typewriter",
    title: "Quick typewriter",
    blurb: "Reveals over a fixed 300 ms, regardless of reply length.",
  },
];

export default function App() {
  const [round, setRound] = useState(0);
  const [landed, setLanded] = useState(false);
  const [waiting, setWaiting] = useState(false);

  const deliver = () => {
    setLanded(false);
    setWaiting(true);
    setRound((r) => r + 1);
    window.setTimeout(() => {
      setWaiting(false);
      setLanded(true);
    }, 300);
  };

  return (
    <main>
      <h1>Rendering a one-burst reply</h1>
      <p className="intro">
        celeris-1 delivers the whole reply at once, typically in about 300 ms.
        Press deliver and compare three ways of putting that on screen.
      </p>
      <button onClick={deliver} disabled={waiting}>
        {waiting ? "waiting 300 ms…" : landed ? "Deliver again" : "Deliver reply"}
      </button>
      <div className="grid">
        {MODES.map(({ mode, title, blurb }) => (
          <section key={mode} className="card">
            <h2>{title}</h2>
            <p className="blurb">{blurb}</p>
            <div className="stage">
              {landed && <BurstReply key={`${mode}-${round}`} text={REPLY} mode={mode} />}
              {waiting && <span className="pending">model working…</span>}
            </div>
          </section>
        ))}
      </div>
    </main>
  );
}
