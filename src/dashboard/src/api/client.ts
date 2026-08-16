export type IssueState =
  | "queued"
  | "claimed"
  | "in_progress"
  | "in_review"
  | "changes_requested"
  | "approved"
  | "merging"
  | "test_failed"
  | "merged";

export interface Issue {
  issue_id: string;
  task_id: string;
  title: string;
  description: string;
  depends_on: string[];
  state: IssueState;
  worker_id: string | null;
  branch: string | null;
  last_activity: string | null;
  updated_at: number;
}

export interface WorkerInfo {
  id: string;
  agent_name: string;
  agent_source: string | null;
  idle: boolean;
}

export interface AppState {
  mode: "supervised" | "autonomous";
  issues: Issue[];
  workers: WorkerInfo[];
}

export interface AgentInfo {
  name: string;
  description: string;
  role: string;
  model: string | null;
  tools: string[];
  prompt: string;
  source: string | null;
  overridden: boolean;
}

export interface WorkspaceFile {
  path: string;
  merged: string | null;   // A / M / D since the seed, via merged work
  editing: string[];       // issue ids with in-flight changes to this file
}

export interface DiffFile {
  status: string;
  path: string;
}

export interface IssueDiff {
  issue_id: string;
  branch: string;
  files: DiffFile[];
  diff: string;
}

export interface BusEvent {
  kind: string;
  event_id: string;
  timestamp: number;
  [key: string]: unknown;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    throw new Error(`${init?.method ?? "GET"} ${path}: ${response.status}`);
  }
  return response.json();
}

export const api = {
  getState: () => request<AppState>("/api/state"),
  submitTask: (prompt: string) =>
    request<{ task_id: string }>("/api/task", {
      method: "POST",
      body: JSON.stringify({ prompt }),
    }),
  getWorkspace: () => request<{ files: WorkspaceFile[] }>("/api/workspace"),
  getDiff: (issueId: string) => request<IssueDiff>(`/api/issues/${issueId}/diff`),
  approve: (issueId: string) =>
    request(`/api/issues/${issueId}/approve`, { method: "POST" }),
  sendBack: (issueId: string, reason: string) =>
    request(`/api/issues/${issueId}/send-back`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  getAgents: () => request<AgentInfo[]>("/api/agents"),
  saveAgent: (name: string, agent: Omit<AgentInfo, "name" | "source" | "overridden">) =>
    request<AgentInfo>(`/api/agents/${name}`, {
      method: "PUT",
      body: JSON.stringify(agent),
    }),
  setMode: (mode: AppState["mode"]) =>
    request<{ mode: AppState["mode"] }>("/api/mode", {
      method: "POST",
      body: JSON.stringify({ mode }),
    }),
};
