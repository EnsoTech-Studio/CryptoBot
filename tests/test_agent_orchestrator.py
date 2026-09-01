from uuid import uuid4
from time import sleep

from app.errors import ApplicationError
from app.services.agent_orchestrator import AgentOrchestrator


def test_orchestrator_requeues_a_temporary_agent_dependency_failure():
    job = {"id": uuid4(), "lease_token": uuid4()}

    class Store:
        def __init__(self):
            self.retried = None

        def claim_agent_job(self, worker_id, lease):
            assert worker_id == "agent-test"
            assert lease.total_seconds() == 120
            return job

        def retry_agent_job(self, job_id, lease_token, error_code):
            self.retried = (job_id, lease_token, error_code)
            return True

        def fail_agent_job(self, *_args):
            raise AssertionError("temporary dependency failure must be retried before terminal failure")

    class UnavailableAuthoring:
        def process_claimed_job(self, _job):
            raise ApplicationError("strategy_design_unavailable", "model unavailable", 503)

    store = Store()

    assert AgentOrchestrator(store, UnavailableAuthoring()).process_once("agent-test") is True
    assert store.retried == (job["id"], job["lease_token"], "strategy_design_unavailable")


def test_orchestrator_heartbeats_a_leased_job_while_authoring_runs():
    job = {"id": uuid4(), "lease_token": uuid4()}

    class Store:
        def __init__(self):
            self.heartbeats = 0

        def claim_agent_job(self, _worker_id, _lease):
            return job

        def heartbeat_agent_job(self, job_id, lease_token, _lease):
            assert (job_id, lease_token) == (job["id"], job["lease_token"])
            self.heartbeats += 1
            return True

    class SlowAuthoring:
        def process_claimed_job(self, _job):
            sleep(0.03)

    store = Store()

    assert AgentOrchestrator(store, SlowAuthoring(), heartbeat_seconds=0.005).process_once("agent-test") is True
    assert store.heartbeats >= 1
