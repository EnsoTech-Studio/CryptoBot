"""Process durable Strategy Authoring jobs outside the HTTP request lifecycle."""

from __future__ import annotations

import os
import signal
from threading import Event

from .config import Settings
from .infrastructure.ai import StrategyDesignHTTPAdapter
from .infrastructure.postgres.store import Store
from .infrastructure.sandbox import DockerSandboxRunner
from .services.agent_orchestrator import AgentOrchestrator
from .services.authoring import StrategyAuthoringService, verify_dsl_backtest


def main() -> int:
    settings = Settings.from_env()
    stop = Event()
    signal.signal(signal.SIGINT, lambda *_args: stop.set())
    signal.signal(signal.SIGTERM, lambda *_args: stop.set())
    store = Store(settings.database_url)
    authoring = StrategyAuthoringService(
        store,
        StrategyDesignHTTPAdapter(settings.ai_service_url, settings.ai_timeout_s),
        DockerSandboxRunner(),
        verify_dsl_backtest,
    )
    orchestrator = AgentOrchestrator(store, authoring, settings.worker_lease_s, settings.worker_heartbeat_s)
    worker_id = os.getenv("AGENT_WORKER_ID", "agent-worker-1").strip() or "agent-worker-1"
    try:
        while not stop.is_set():
            if not orchestrator.process_once(worker_id):
                stop.wait(0.5)
    finally:
        authoring.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
