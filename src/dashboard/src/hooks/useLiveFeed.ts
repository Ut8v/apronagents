import { useCallback, useEffect, useRef, useState } from "react";
import { api, AppState, BusEvent } from "../api/client";

const MAX_EVENTS = 200;

/**
 * The dashboard's single source of truth: the current bus state plus the
 * live event stream. Every event triggers a (debounced) state refetch, so
 * the UI only ever renders what the store reports.
 */
export function useLiveFeed() {
  const [state, setState] = useState<AppState | null>(null);
  const [events, setEvents] = useState<BusEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const refreshTimer = useRef<number | undefined>(undefined);

  const refresh = useCallback(() => {
    window.clearTimeout(refreshTimer.current);
    refreshTimer.current = window.setTimeout(() => {
      api.getState().then(setState).catch(() => undefined);
    }, 150);
  }, []);

  useEffect(() => {
    let socket: WebSocket | null = null;
    let retryTimer: number | undefined;
    let closed = false;

    const connect = () => {
      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(`${protocol}://${window.location.host}/ws`);
      socket.onopen = () => setConnected(true);
      socket.onmessage = (message) => {
        const payload = JSON.parse(message.data);
        if (payload.type === "snapshot") {
          setState(payload.state);
        } else if (payload.type === "event") {
          setEvents((existing) =>
            [payload.event, ...existing].slice(0, MAX_EVENTS),
          );
          refresh();
        }
      };
      socket.onclose = () => {
        setConnected(false);
        if (!closed) {
          retryTimer = window.setTimeout(connect, 1000);
        }
      };
    };

    connect();
    return () => {
      closed = true;
      window.clearTimeout(retryTimer);
      window.clearTimeout(refreshTimer.current);
      socket?.close();
    };
  }, [refresh]);

  return { state, events, connected, refresh };
}
