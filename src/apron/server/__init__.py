"""Server organ: serves the dashboard, exposes REST for review actions, and
streams the live event feed over WebSocket. The dashboard renders bus state
only; it never holds its own source of truth."""
