import { BusEvent } from "../api/client";

function describe(event: BusEvent): string {
  const parts = [event.kind];
  if (typeof event.issue_id === "string") parts.push(event.issue_id);
  if (typeof event.worker_id === "string") parts.push(`by ${event.worker_id}`);
  if (typeof event.branch === "string") parts.push(`(${event.branch})`);
  return parts.join(" ");
}

export default function LiveFeed({ events }: { events: BusEvent[] }) {
  return (
    <section>
      <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
        Live feed
      </h2>
      {events.length === 0 ? (
        <p className="text-sm text-slate-600">no events yet</p>
      ) : (
        <ul className="max-h-72 space-y-1 overflow-auto font-mono text-xs">
          {events.map((event) => (
            <li key={event.event_id} className="flex gap-2 text-slate-400">
              <span className="shrink-0 text-slate-600">
                {new Date(event.timestamp * 1000).toLocaleTimeString()}
              </span>
              <span className="truncate">{describe(event)}</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
