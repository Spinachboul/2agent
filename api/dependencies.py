
from functools import lru_cache

from agents.supervisor import SupervisorAgent
from agents.copilot_agent import CopilotAgent
from services.extractor_service import ExtractorService


@lru_cache(maxsize=1)
def get_supervisor() -> SupervisorAgent:
    # ExtractorService automatically locates the root-level extractor.py.
    extractor = ExtractorService()
    return SupervisorAgent(extractor)


@lru_cache(maxsize=1)
def get_copilot() -> CopilotAgent:
    return CopilotAgent()
