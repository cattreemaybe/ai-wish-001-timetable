"""AI-WISH-001 independent timetabling engine."""
from .data_gen import build_all_scenarios, build_scenario, scenario_summaries
from .domain import Scenario, default_time_model
from .runner import run_scenario, validate_result
from .validator import validate_schedule
from .tools import describe_tools

__all__ = [
    "Scenario", "build_all_scenarios", "build_scenario", "scenario_summaries",
    "run_scenario", "validate_result", "validate_schedule", "default_time_model",
    "describe_tools",
]
__version__ = "0.1.0"
