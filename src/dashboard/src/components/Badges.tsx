import { IssueState } from "../api/client";

/** The single source of truth for the 9-state color system: chips, queue
 * bars, and feed markers all derive from this table. */
export const STATE_META: Record<
  IssueState,
  { label: string; l: number; c: number; h: number }
> = {
  queued: { label: "queued", l: 0.62, c: 0.012, h: 255 },
  claimed: { label: "claimed", l: 0.68, c: 0.08, h: 268 },
  in_progress: { label: "in progress", l: 0.74, c: 0.1, h: 205 },
  in_review: { label: "in review", l: 0.8, c: 0.11, h: 78 },
  changes_requested: { label: "changes req", l: 0.74, c: 0.12, h: 45 },
  approved: { label: "approved", l: 0.76, c: 0.1, h: 152 },
  merging: { label: "merging", l: 0.74, c: 0.1, h: 296 },
  test_failed: { label: "tests failed", l: 0.68, c: 0.14, h: 25 },
  merged: { label: "merged", l: 0.62, c: 0.045, h: 152 },
};

export function stateColor(state: IssueState, alpha?: number): string {
  const { l, c, h } = STATE_META[state];
  return `oklch(${l} ${c} ${h}${alpha !== undefined ? ` / ${alpha}` : ""})`;
}

const PULSING: Set<IssueState> = new Set(["in_progress", "merging"]);

export function StateChip({ state }: { state: IssueState }) {
  const { label, l, c, h } = STATE_META[state];
  return (
    <span
      className="inline-flex items-center gap-1.5 whitespace-nowrap rounded-[5px] py-[2px] pl-[7px] pr-2 font-mono text-[10px] uppercase tracking-[0.08em]"
      style={{
        background: stateColor(state, 0.13),
        border: `1px solid ${stateColor(state, 0.42)}`,
        color: `oklch(${Math.min(0.9, l + 0.08)} ${c} ${h})`,
      }}
    >
      <span
        className={`h-[5px] w-[5px] rounded-full ${PULSING.has(state) ? "animate-pulse-dot" : ""}`}
        style={{ background: stateColor(state) }}
      />
      {label}
    </span>
  );
}

const SOURCE_HUES: Record<string, number> = {
  shipped: 255,
  user: 205,
  project: 296,
  "claude-user": 78,
  "claude-project": 152,
};

export function SourceBadge({ source }: { source: string | null }) {
  if (!source) return null;
  const hue = SOURCE_HUES[source] ?? 255;
  return (
    <span
      className="rounded-[4px] px-[7px] py-[1.5px] font-mono text-[9.5px] uppercase tracking-[0.08em]"
      style={{
        background: `oklch(0.7 0.06 ${hue} / 0.12)`,
        border: `1px solid oklch(0.7 0.06 ${hue} / 0.34)`,
        color: `oklch(0.78 0.05 ${hue})`,
      }}
    >
      {source}
    </span>
  );
}

const FILE_STATUS_COLORS: Record<string, string> = {
  M: "oklch(0.78 0.1 78)",
  A: "oklch(0.74 0.1 152)",
  D: "oklch(0.68 0.13 25)",
  R: "oklch(0.74 0.09 296)",
};

export function FileStatusSquare({ status }: { status: string }) {
  const letter = status.charAt(0);
  const color = FILE_STATUS_COLORS[letter] ?? "oklch(0.7 0.01 255)";
  return (
    <span
      className="inline-flex h-3.5 w-3.5 items-center justify-center rounded-[3px] text-[9.5px] font-bold"
      style={{ color, background: `${color.slice(0, -1)} / 0.16)` }}
    >
      {letter}
    </span>
  );
}
