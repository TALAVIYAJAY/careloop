import logging
from typing import List, Dict, Any, Optional

from clinic_db.database import ClinicDatabase
from agent.clinic_agent import ClinicAgent
from agent.state import PatientSession
from .scenarios import EvaluationScenario, BENCHMARK_SCENARIOS
from .judge import DualLayerJudge
from .rubric import ScenarioEvaluationResult, SuiteEvaluationSummary

logger = logging.getLogger("careloop.eval")


class EvaluationHarness:
    """
    Test harness that runs benchmark clinical scenarios against the agent,
    enforcing clean database isolation and collecting Dual-Layer evaluation results.
    """

    def __init__(
        self,
        db: Optional[ClinicDatabase] = None,
        judge: Optional[DualLayerJudge] = None,
        scenarios: Optional[List[EvaluationScenario]] = None
    ):
        self.db = db or ClinicDatabase()
        self.judge = judge or DualLayerJudge()
        self.scenarios = scenarios or BENCHMARK_SCENARIOS

    def evaluate_scenario(
        self,
        scenario: Any,
        agent: ClinicAgent
    ) -> ScenarioEvaluationResult:
        """
        Executes a single scenario against the provided agent with clean DB isolation.
        Accepts either an EvaluationScenario object or a scenario_id string.
        """
        if isinstance(scenario, str):
            target = next((s for s in self.scenarios if s.id == scenario), None)
            if not target:
                raise ValueError(f"Scenario ID {scenario} not found in harness scenarios.")
            scenario = target

        # 1. Reset clinic database to pristine seed state
        self.db.reset_database()

        # 2. Initialize clean patient session
        session = PatientSession(
            session_id=f"SESS_EVAL_{scenario.id}",
            patient_name=scenario.patient_name,
            patient_phone=scenario.patient_phone
        )

        # 3. Simulate multi-turn dialogue
        for turn in scenario.dialogue_script:
            agent.handle_turn(session, turn.user_input)

        # 4. Evaluate with Dual-Layer Judge
        return self.judge.evaluate_scenario(scenario, session, self.db)

    def run_suite(self, agent: ClinicAgent) -> SuiteEvaluationSummary:
        """
        Executes all scenarios in the benchmark suite against the provided agent.
        Guarantees clean DB resets between scenarios to avoid cross-contamination.
        """
        results: List[ScenarioEvaluationResult] = []

        for scenario in self.scenarios:
            results.append(self.evaluate_scenario(scenario, agent))

        # 5. Compile suite statistics
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        composite = round(sum(r.total_score for r in results) / total, 1) if total > 0 else 0.0
        pass_rate = round((passed / total) * 100, 1) if total > 0 else 0.0

        return SuiteEvaluationSummary(
            total_scenarios=total,
            passed_scenarios=passed,
            failed_scenarios=failed,
            composite_score=composite,
            scenario_results=results,
            pass_rate_percentage=pass_rate
        )
