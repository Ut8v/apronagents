import { BusEvent } from "../api/client";

const EVENT_HUES: Record<string, number> = {
  TaskReceived: 205,
  TaskPlanned: 205,
  WorkStarted: 205,
  IssueQueued: 255,
  WorkerStarted: 255,
  AgentDefinitionsReloaded: 255,
  IssueClaimed: 268,
  HandoffCompleted: 268,
  ReviewOpened: 78,
  ChangesRequested: 45,
  ReviewApproved: 152,
  TestsPassed: 152,
  MergeSucceeded: 152,
  TaskCompleted: 152,
  MergeStarted: 296,
  TestsFailed: 25,
  MergeConflictDetected: 25,
};

function detail(event: BusEvent): string {
  const parts: string[] = [];
  if (typeof event.issue_id === "string") parts.push(event.issue_id);
  if (typeof event.worker_id === "string") parts.push(`by ${event.worker_id}`);
  if (typeof event.branch === "string") parts.push(`(${event.branch})`);
  return parts.join(" ");
}

function FeedRow({ event }: { event: BusEvent }) {
  const hue = EVENT_HUES[event.kind] ?? 255;
  return (
    <div
      className="grid animate-in-row items-baseline gap-[9px] border-b border-[oklch(0.22_0.011_255)] px-[11px] py-[7px] last:border-b-0"
      style={{ gridTemplateColumns: "52px 10px minmax(0,1fr)" }}
    >
      <span className="font-mono text-[10.5px] text-faint">
        {new Date(event.timestamp * 1000).toLocaleTimeString([], {
          hour12: false,
        })}
      </span>
      <span
        className="mt-1 h-1.5 w-1.5 rounded-full"
        style={{ background: `oklch(0.72 0.08 ${hue})` }}
      />
      <span className="break-words font-mono text-[11px] text-[oklch(0.72_0.012_255)]">
        <span style={{ color: `oklch(0.82 0.07 ${hue})` }}>{event.kind}</span>{" "}
        {detail(event)}
      </span>
    </div>
  );
}

export default function LiveFeed({ events: allEvents }: { events: BusEvent[] }) {
  // Progress chatter lives on the worker cards; the feed keeps lifecycle facts.
  // Streaming telemetry has its own surfaces (worker cards, the dispatch
  // terminal); the feed keeps to state transitions.
  const events = allEvents.filter(
    (e) => e.kind !== "ProgressReported" && e.kind !== "PlanningProgress",
  );
  return (
    <section className="flex min-h-0 flex-1 flex-col">
      <div className="mb-2.5 flex items-center gap-3">
        <span className="whitespace-nowrap font-mono text-[10px] uppercase tracking-[0.16em] text-[oklch(0.66_0.012_255)]">
          live feed
        </span>
        <span className="h-px flex-1 bg-[oklch(0.26_0.013_255)]" />
        <span className="h-[5px] w-[5px] animate-pulse-slow rounded-full bg-[oklch(0.75_0.1_205)]" />
      </div>
      {events.length === 0 ? (
        <div className="flex items-center gap-3 rounded-[10px] border border-dashed border-[oklch(0.3_0.013_255)] p-4">
          <span className="h-2 w-2 rounded-full border border-[oklch(0.4_0.012_255)]" />
          <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-[oklch(0.55_0.012_255)]">
            no events yet
          </span>
        </div>
      ) : (
        <div className="min-h-0 flex-1 overflow-auto rounded-[10px] border border-line bg-[oklch(0.185_0.011_255)]">
          {events.map((event) => (
            <FeedRow key={event.event_id} event={event} />
          ))}
        </div>
      )}
    </section>
  );
}
