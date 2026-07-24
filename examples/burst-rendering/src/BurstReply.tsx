import { useEffect, useState } from "react";

// Renders a reply that arrived whole, the way celeris-1 delivers. Three
// treatments:
//
//   instant:    show the full reply the moment it lands. The honest default.
//   fade:       one quick opacity/translate transition (about 180 ms). Adds
//               a sense of arrival without delaying anything meaningful.
//   typewriter: reveal characters over a FIXED total duration (about 300 ms
//               regardless of length), for products whose users expect text
//               to "arrive". Never scale duration by length; a long reply
//               must not read slower than a short one.
//
// All three collapse to instant when the user prefers reduced motion.

export type BurstMode = "instant" | "fade" | "typewriter";

const TYPEWRITER_TOTAL_MS = 300;
const FADE_MS = 180;

function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(query.matches);
    const onChange = () => setReduced(query.matches);
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);
  return reduced;
}

export default function BurstReply({ text, mode }: { text: string; mode: BurstMode }) {
  const reducedMotion = useReducedMotion();
  const effectiveMode: BurstMode = reducedMotion ? "instant" : mode;
  const [revealed, setRevealed] = useState(0);
  const [faded, setFaded] = useState(false);

  useEffect(() => {
    setRevealed(0);
    setFaded(false);
    if (effectiveMode === "fade") {
      const raf = requestAnimationFrame(() => setFaded(true));
      return () => cancelAnimationFrame(raf);
    }
    if (effectiveMode === "typewriter") {
      // Position from elapsed time, not accumulation: every tick computes
      // the reveal from the clock, so throttled, dropped, or delayed ticks
      // never stretch the fixed total duration. An interval (not
      // requestAnimationFrame) keeps it completing even in hidden or
      // heavily throttled tabs.
      const startedAt = performance.now();
      const timer = window.setInterval(() => {
        const fraction = Math.min(1, (performance.now() - startedAt) / TYPEWRITER_TOTAL_MS);
        setRevealed(Math.round(fraction * text.length));
        if (fraction >= 1) window.clearInterval(timer);
      }, 40);
      return () => window.clearInterval(timer);
    }
    return undefined;
  }, [text, effectiveMode]);

  if (effectiveMode === "typewriter") {
    return <p className="reply">{text.slice(0, revealed)}</p>;
  }
  if (effectiveMode === "fade") {
    return (
      <p
        className="reply"
        style={{
          opacity: faded ? 1 : 0,
          transform: faded ? "none" : "translateY(4px)",
          transition: `opacity ${FADE_MS}ms ease, transform ${FADE_MS}ms ease`,
        }}
      >
        {text}
      </p>
    );
  }
  return <p className="reply">{text}</p>;
}
