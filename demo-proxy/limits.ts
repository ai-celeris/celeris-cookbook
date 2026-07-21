// In-memory rate limiting for the demo proxy: a global token bucket (protects
// the shared Celeris key) plus a per-IP fixed window (stops one visitor from
// draining the bucket). Deliberately process-local — the demo runs as a
// single container; use a shared store only if that ever changes.

export class TokenBucket {
  private tokens: number;
  private lastRefill = Date.now();

  constructor(
    private readonly ratePerSecond: number,
    private readonly burst: number,
  ) {
    this.tokens = burst;
  }

  take(): boolean {
    const now = Date.now();
    this.tokens = Math.min(
      this.burst,
      this.tokens + ((now - this.lastRefill) / 1000) * this.ratePerSecond,
    );
    this.lastRefill = now;
    if (this.tokens >= 1) {
      this.tokens -= 1;
      return true;
    }
    return false;
  }
}

export class PerIpWindow {
  private counts = new Map<string, { windowStart: number; count: number }>();

  constructor(
    private readonly limitPerWindow: number,
    private readonly windowMs = 60_000,
  ) {}

  take(ip: string): boolean {
    const now = Date.now();
    const entry = this.counts.get(ip);
    if (!entry || now - entry.windowStart >= this.windowMs) {
      this.counts.set(ip, { windowStart: now, count: 1 });
      this.prune(now);
      return true;
    }
    if (entry.count >= this.limitPerWindow) return false;
    entry.count += 1;
    return true;
  }

  private prune(now: number): void {
    if (this.counts.size < 10_000) return;
    for (const [ip, entry] of this.counts) {
      if (now - entry.windowStart >= this.windowMs) this.counts.delete(ip);
    }
  }
}
