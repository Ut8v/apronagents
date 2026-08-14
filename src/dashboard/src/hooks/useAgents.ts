import { useCallback, useEffect, useState } from "react";
import { AgentInfo, api } from "../api/client";

/** The resolved agent set, with save-through-the-overlay editing. */
export function useAgents() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(() => {
    api
      .getAgents()
      .then(setAgents)
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(reload, [reload]);

  const save = useCallback(
    async (name: string, agent: Omit<AgentInfo, "name" | "source" | "overridden">) => {
      await api.saveAgent(name, agent);
      reload();
    },
    [reload],
  );

  return { agents, error, reload, save };
}
