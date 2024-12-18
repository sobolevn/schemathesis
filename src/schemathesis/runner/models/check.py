from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import cached_property
from itertools import groupby
from typing import TYPE_CHECKING, Any, Generator, Iterator

from schemathesis.core.failures import Failure
from schemathesis.core.transport import Response

from .status import Status
from .transport import Request

if TYPE_CHECKING:
    from schemathesis.generation.case import Case


@dataclass(repr=False)
class Check:
    """Single check run result."""

    name: str
    status: Status
    request: Request
    response: Response
    case: Case
    failure: Failure | None = None

    @cached_property
    def code_sample(self) -> str:
        return self.case.as_curl_command(
            headers={key: value[0] for key, value in self.request.headers.items()}, verify=self.response.verify
        )

    def asdict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "request": {
                "method": self.request.method,
                "uri": self.request.uri,
                "body": self.request.encoded_body,
                "headers": self.request.headers,
            },
            "response": self.response.asdict(),
            "case": self.case.asdict(),
            "failure": asdict(self.failure) if self.failure is not None else None,  # type: ignore
        }


def group_failures_by_code_sample(checks: list[Check]) -> Generator[tuple[str, Iterator[Check]], None, None]:
    deduplicated = {check.failure: check for check in checks if check.failure is not None}
    failures = sorted(deduplicated.values(), key=_by_unique_key)
    for (sample, _, _), gen in groupby(failures, _by_unique_key):
        yield (sample, gen)


def _by_unique_key(check: Check) -> tuple[str, int, bytes]:
    return (
        check.code_sample,
        check.response.status_code,
        check.response.content or b"SCHEMATHESIS-INTERNAL-EMPTY-BODY",
    )
