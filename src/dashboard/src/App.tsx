import { useEffect, useState } from "react";
import { api } from "./api/client";
import { useLiveFeed } from "./hooks/useLiveFeed";
import AgentBoard from "./components/AgentBoard";
import AgentsView from "./components/AgentsView";
import LiveFeed from "./components/LiveFeed";
import MergeQueue from "./components/MergeQueue";
import ReviewCard from "./components/ReviewCard";
import TaskBar from "./components/TaskBar";
import WorkspaceTree from "./components/WorkspaceTree";

type View = "board" | "agents";

export default function App() {
  const { state, events, connected, refresh } = useLiveFeed();
  const [view, setView] = useState<View>("board");
  const [armedIssueId, setArmedIssueId] = useState<string | null>(null);
  const [showTree, setShowTree] = useState(true);

  const reviews = state?.issues.filter((i) => i.state === "in_review") ?? [];

  // Disarm when the armed issue leaves review, and on Escape.
  useEffect(() => {
    if (armedIssueId && !reviews.some((i) => i.issue_id === armedIssueId)) {
      setArmedIssueId(null);
    }
  }, [reviews, armedIssueId]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setArmedIssueId(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const toggleMode = async () => {
    if (!state) return;
    await api.setMode(state.mode === "supervised" ? "autonomous" : "supervised");
    refresh();
  };
  const modeHue = state?.mode === "supervised" ? 78 : 152;

  return (
    <div className="min-h-screen">
      <header
        className="sticky top-0 z-20 flex h-14 items-center gap-5 border-b border-line px-5 backdrop-blur-md"
        style={{ background: "oklch(0.175 0.011 255 / 0.92)" }}
      >
        <div className="flex items-center gap-2.5">
          <img src="/mark-reverse.svg" alt="" className="h-7 w-7" />
          <span className="text-sm font-[650] tracking-[0.02em] text-ink">Apron Agents</span>
          <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-dim">
            merge cockpit
          </span>
        </div>
        <span className="flex items-center gap-2 rounded-full border border-line bg-[oklch(0.19_0.011_255)] px-2.5 py-1">
          <span
            className="h-[7px] w-[7px] animate-pulse-slow rounded-full"
            style={{
              background: connected ? "oklch(0.75 0.13 152)" : "oklch(0.65 0.16 25)",
              boxShadow: `0 0 10px ${connected ? "oklch(0.75 0.13 152 / 0.7)" : "oklch(0.65 0.16 25 / 0.7)"}`,
            }}
          />
          <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[oklch(0.66_0.012_255)]">
            {connected ? "linked" : "no link"}
          </span>
        </span>
        <nav className="flex gap-0.5 rounded-lg border border-[oklch(0.26_0.013_255)] bg-[oklch(0.19_0.011_255)] p-[3px]">
          {(["board", "agents"] as View[]).map((name) => (
            <button
              key={name}
              onClick={() => setView(name)}
              className={`rounded-md border px-3.5 py-1.5 font-mono text-[11px] uppercase tracking-[0.1em] transition-colors ${
                view === name
                  ? "border-[oklch(0.34_0.02_205)] bg-[oklch(0.26_0.025_205)] text-[oklch(0.93_0.02_205)]"
                  : "border-transparent text-[oklch(0.62_0.012_255)]"
              }`}
            >
              {name}
            </button>
          ))}
        </nav>
        <div className="ml-auto">
          {state && (
            <button
              onClick={toggleMode}
              className="flex h-8 items-center gap-2 rounded-full px-3.5 font-mono text-[11px] uppercase tracking-[0.08em]"
              style={{
                background: `oklch(0.7 0.1 ${modeHue} / 0.13)`,
                border: `1px solid oklch(0.7 0.1 ${modeHue} / 0.45)`,
                color: `oklch(0.82 0.1 ${modeHue})`,
              }}
              title="toggle merge gating"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-current" />
              {state.mode}
            </button>
          )}
        </div>
      </header>

      {view === "board" ? (
        <div
          className={`grid min-h-[calc(100vh-56px)] gap-px bg-line ${
            showTree
              ? "lg:grid-cols-[232px_minmax(0,1fr)_384px]"
              : "lg:grid-cols-[20px_minmax(0,1fr)_384px]"
          }`}
        >
          <aside className="relative flex flex-col bg-rail py-4 pl-2 pr-3 lg:sticky lg:top-14 lg:h-[calc(100vh-56px)]">
            <button
              onClick={() => setShowTree(!showTree)}
              title={showTree ? "collapse workspace" : "expand workspace"}
              className="absolute -right-0 top-1/2 z-10 flex h-12 w-4 -translate-y-1/2 items-center justify-center rounded-l border border-r-0 border-[oklch(0.3_0.014_255)] bg-[oklch(0.19_0.011_255)] font-mono text-[9px] text-[oklch(0.6_0.012_255)] hover:text-[oklch(0.9_0.008_255)]"
            >
              {showTree ? "◂" : "▸"}
            </button>
            {showTree && state && (
              <WorkspaceTree
                refreshKey={state.issues.map((i) => i.issue_id + i.state + i.updated_at).join("|")}
              />
            )}
          </aside>
          <div className="flex flex-col gap-5 bg-base p-5">
            <TaskBar />
            {state && (
              <>
                <AgentBoard state={state} />
                <section>
                  <div className="mb-2.5 flex items-center gap-3">
                    <span className="whitespace-nowrap font-mono text-[10px] uppercase tracking-[0.16em] text-[oklch(0.84_0.1_78)]">
                      awaiting review
                    </span>
                    {reviews.length > 0 && (
                      <span className="inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-[5px] border border-[oklch(0.78_0.11_78/0.4)] bg-[oklch(0.78_0.11_78/0.16)] px-1 font-mono text-[10px] text-[oklch(0.86_0.1_78)]">
                        {reviews.length}
                      </span>
                    )}
                    <span
                      className="h-px flex-1"
                      style={{
                        background:
                          "linear-gradient(90deg, oklch(0.78 0.11 78 / 0.35), oklch(0.26 0.013 255))",
                      }}
                    />
                    <span className="font-mono text-[10px] uppercase tracking-[0.1em] text-[oklch(0.55_0.012_255)]">
                      clearance required
                    </span>
                  </div>
                  {reviews.length === 0 ? (
                    <div className="flex items-center gap-3 rounded-xl border border-dashed border-[oklch(0.3_0.013_255)] p-[26px]">
                      <span className="h-2 w-2 rounded-full border border-[oklch(0.4_0.012_255)]" />
                      <span className="font-mono text-[11px] uppercase tracking-[0.08em] text-[oklch(0.55_0.012_255)]">
                        pattern clear — no reviews holding
                      </span>
                    </div>
                  ) : (
                    <div className="flex flex-col gap-4">
                      {reviews.map((issue) => (
                        <ReviewCard
                          key={issue.issue_id}
                          issue={issue}
                          armed={armedIssueId === issue.issue_id}
                          onArm={() => setArmedIssueId(issue.issue_id)}
                          onDisarm={() => setArmedIssueId(null)}
                          onAction={refresh}
                        />
                      ))}
                    </div>
                  )}
                </section>
              </>
            )}
          </div>
          <aside className="flex flex-col gap-5 bg-rail px-4 py-5 lg:sticky lg:top-14 lg:h-[calc(100vh-56px)]">
            {state && <MergeQueue state={state} />}
            <LiveFeed events={events} />
          </aside>
        </div>
      ) : (
        <AgentsView />
      )}
    </div>
  );
}
