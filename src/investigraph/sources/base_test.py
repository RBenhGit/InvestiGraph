import pytest
from pydantic import ValidationError

from investigraph.sources.base import Capability
from investigraph.template.models import Market, Period


def _capability() -> Capability:
    return Capability(
        markets={Market.US},
        periods={Period.ANNUAL},
        max_history={Period.ANNUAL: 4},
        metrics={"price"},
    )


def test_capability_is_immutable():
    cap = _capability()
    with pytest.raises(Exception):
        cap.metrics = {"revenue"}


def test_capability_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        Capability(
            markets={Market.US},
            periods={Period.ANNUAL},
            max_history={Period.ANNUAL: 4},
            metrics={"price"},
            typo_field="oops",
        )
