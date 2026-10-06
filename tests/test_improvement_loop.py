import pytest
from clinic_db.database import ClinicDatabase
from improvement.self_improver import SelfImprovementCoordinator
from improvement.memory_store import DirectiveStore


def test_full_improvement_loop_execution(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    db = ClinicDatabase(db_path=":memory:")
    store = DirectiveStore()
    coordinator = SelfImprovementCoordinator(db=db, store=store)

    result = coordinator.run_cycle()

    # Verify baseline run executed
    assert result.baseline_summary.total_scenarios == 5
    # Verify improved run executed
    assert result.improved_summary.total_scenarios == 5

    # Verify score moved or stayed high
    assert result.improved_summary.composite_score >= result.baseline_summary.composite_score

    # Verify zero regressions
    assert result.regressions_detected == 0
    assert result.loop_closed_successfully is True
