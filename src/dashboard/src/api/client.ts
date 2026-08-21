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

export interface PlanningState {
  active: boolean;
  notes: string[];
}

export interface PlanIssue {
  id: string;
  title: string;
  description: string;
  depends_on: string[];
}

export interface PlanReviewState {
  task_id: string;
  issues: PlanIssue[];
}

export interface AppState {
  mode: "supervised" | "autonomous";
  planning: PlanningState;
  plan_review: PlanReviewState | null;
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

export interface DiffAnnotation {
  path: string;
  line: number;
  note: string;
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
  approvePlan: (taskId: string, issues: PlanIssue[]) =>
    request("/api/plan/approve", {
      method: "POST",
      body: JSON.stringify({ task_id: taskId, issues }),
    }),
  getDiff: (issueId: string) => request<IssueDiff>(`/api/issues/${encodeURIComponent(issueId)}/diff`),
  approve: (issueId: string) =>
    request(`/api/issues/${encodeURIComponent(issueId)}/approve`, { method: "POST" }),
  sendBack: (issueId: string, reason: string, annotations: DiffAnnotation[] = []) =>
    request(`/api/issues/${encodeURIComponent(issueId)}/send-back`, {
      method: "POST",
      body: JSON.stringify({ reason, annotations }),
    }),
  getAgents: () => request<AgentInfo[]>("/api/agents"),
  saveAgent: (name: string, agent: Omit<AgentInfo, "name" | "source" | "overridden">) =>
    request<AgentInfo>(`/api/agents/${encodeURIComponent(name)}`, {
      method: "PUT",
      body: JSON.stringify(agent),
    }),
  setMode: (mode: AppState["mode"]) =>
    request<{ mode: AppState["mode"] }>("/api/mode", {
      method: "POST",
      body: JSON.stringify({ mode }),
    }),
};
