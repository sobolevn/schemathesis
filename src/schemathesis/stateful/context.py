from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from schemathesis.core import NOT_SET, NotSet
from schemathesis.core.failures import Failure
from schemathesis.core.transport import Response
from schemathesis.generation.targets import TargetMetricCollector

from . import events

if TYPE_CHECKING:
    from schemathesis.generation.case import Case

    from ..runner.models import Check


@dataclass
class RunnerContext:
    """Mutable context for state machine execution."""

    # All seen failure keys, both grouped and individual ones
    seen_in_run: set[Failure] = field(default_factory=set)
    # Failures keys seen in the current suite
    seen_in_suite: set[Failure] = field(default_factory=set)
    # Unique failures collected in the current suite
    failures_for_suite: list[Check] = field(default_factory=list)
    # All checks executed in the current run
    checks_for_step: list[Check] = field(default_factory=list)
    # Status of the current step
    current_step_status: events.StepStatus | None = None
    # The currently processed response
    current_response: Response | None = None
    # Total number of failures
    failures_count: int = 0
    # The total number of completed test scenario
    completed_scenarios: int = 0
    # Metrics collector for targeted testing
    metric_collector: TargetMetricCollector = field(default_factory=TargetMetricCollector)
    step_outcomes: dict[int, BaseException | None] = field(default_factory=dict)

    @property
    def current_scenario_status(self) -> events.ScenarioStatus:
        if self.current_step_status == events.StepStatus.SUCCESS:
            return events.ScenarioStatus.SUCCESS
        if self.current_step_status == events.StepStatus.FAILURE:
            return events.ScenarioStatus.FAILURE
        if self.current_step_status == events.StepStatus.ERROR:
            return events.ScenarioStatus.ERROR
        if self.current_step_status == events.StepStatus.INTERRUPTED:
            return events.ScenarioStatus.INTERRUPTED
        return events.ScenarioStatus.REJECTED

    def reset_scenario(self) -> None:
        self.completed_scenarios += 1
        self.current_step_status = None
        self.current_response = None
        self.step_outcomes.clear()

    def reset_step(self) -> None:
        self.checks_for_step = []

    def step_succeeded(self) -> None:
        self.current_step_status = events.StepStatus.SUCCESS

    def step_failed(self) -> None:
        self.current_step_status = events.StepStatus.FAILURE

    def step_errored(self) -> None:
        self.current_step_status = events.StepStatus.ERROR

    def step_interrupted(self) -> None:
        self.current_step_status = events.StepStatus.INTERRUPTED

    def mark_as_seen_in_run(self, exc: Failure) -> None:
        self.seen_in_run.add(exc)

    def mark_as_seen_in_suite(self, exc: Failure) -> None:
        self.seen_in_suite.add(exc)

    def mark_current_suite_as_seen_in_run(self) -> None:
        self.seen_in_run.update(self.seen_in_suite)

    def is_seen_in_run(self, exc: Failure) -> bool:
        return exc in self.seen_in_run

    def is_seen_in_suite(self, exc: Failure) -> bool:
        return exc in self.seen_in_suite

    def add_failed_check(self, check: Check) -> None:
        self.failures_for_suite.append(check)
        self.failures_count += 1

    def collect_metric(self, case: Case, response: Response) -> None:
        self.metric_collector.store(case, response)

    def maximize_metrics(self) -> None:
        self.metric_collector.maximize()

    def reset(self) -> None:
        self.failures_for_suite = []
        self.seen_in_suite.clear()
        self.reset_scenario()
        self.metric_collector.reset()

    def store_step_outcome(self, case: Case, outcome: BaseException | None) -> None:
        self.step_outcomes[hash(case)] = outcome

    def get_step_outcome(self, case: Case) -> BaseException | None | NotSet:
        return self.step_outcomes.get(hash(case), NOT_SET)
