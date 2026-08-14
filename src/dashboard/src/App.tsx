import { useState } from "react";
import { api } from "./api/client";
import { useLiveFeed } from "./hooks/useLiveFeed";
import AgentBoard from "./components/AgentBoard";
import AgentsView from "./components/AgentsView";
import LiveFeed from "./components/LiveFeed";
import MergeQueue from "./components/MergeQueue";
import ReviewCard from "./components/ReviewCard";
import TaskBar from "./components/TaskBar";

type Tab = "board" | "agents";

export default function App() {
  const { state, events, connected, refresh } = useLiveFeed();
  const [tab, setTab] = useState<Tab>("board");

  const toggleMode = async () => {
    if (!state) return;
    await api.setMode(state.mode === "supervised" ? "autonomous" : "supervised");
    refresh();
  };

  const reviews = state?.issues.filter((i) => i.state === "in_review") ?? [];

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <header className="border-b border-slate-800 px-6 py-3">
        <div className="mx-auto flex max-w-6xl items-center gap-4">
          <h1 className="text-lg font-semibold">Apron Agents</h1>
          <span
            className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-400" : "bg-red-500"}`}
            title={connected ? "live" : "disconnected"}
          />
          <nav className="flex gap-1 text-sm">
            {(["board", "agents"] as Tab[]).map((name) => (
              <button
                key={name}
                onClick={() => setTab(name)}
                className={`rounded px-3 py-1 capitalize ${
                  tab === name ? "bg-slate-800" : "text-slate-400 hover:text-slate-200"
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
                className={`rounded border px-3 py-1 text-sm ${
                  state.mode === "supervised"
                    ? "border-amber-600 text-amber-300"
                    : "border-emerald-600 text-emerald-300"
                }`}
                title="toggle merge gating"
              >
                {state.mode}
              </button>
            )}
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-6xl space-y-6 px-6 py-6">
        {tab === "board" ? (
          <>
            <TaskBar />
            {state && (
              <>
                <AgentBoard state={state} />
                {reviews.length > 0 && (
                  <section>
                    <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-slate-500">
                      Awaiting review
                    </h2>
                    <div className="space-y-3">
                      {reviews.map((issue) => (
                        <ReviewCard key={issue.issue_id} issue={issue} onAction={refresh} />
                      ))}
                    </div>
                  </section>
                )}
                <div className="grid gap-6 lg:grid-cols-2">
                  <MergeQueue state={state} />
                  <LiveFeed events={events} />
                </div>
              </>
            )}
          </>
        ) : (
          <AgentsView />
        )}
      </div>
    </main>
  );
}
