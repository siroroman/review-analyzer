from collections.abc import Mapping
from datetime import timedelta
from decimal import Decimal
from typing import Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.pipeline import RunReport
from app.transport import read_secret


class Reporter(Protocol):
    """The part of `pipeline` the API uses: what the dashboard shows of a Run."""

    def report(self, run_id: str) -> RunReport:
        """Raises `UnknownRun`."""
        ...


class ApiConfig(BaseModel):
    """Tokens and limits of the API.

    `demo_tokens` open the Demo routes, `admin_token` alone opens `/admin/*`; the two never mix. Limits are
    counted in the memory of one process: with several instances each keeps its own count.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    demo_tokens: tuple[SecretStr, ...] = Field(min_length=1)
    admin_token: SecretStr | None = None
    requests_per_minute: int = Field(default=60, gt=0)
    runs_per_day: int = Field(default=5, gt=0)
    cache_ttl: timedelta = timedelta(hours=24)
    monthly_cap: Decimal = Field(default=Decimal(30), gt=0)  # USD, shown on the admin screen
    run_cap: str = "1"
    autocomplete_run_id: str = "autocomplete"  # prefix: each search or confirm gets "<prefix>-<n>"

    @classmethod
    def from_environ(cls, environ: Mapping[str, str]) -> Self:
        """`DEMO_TOKENS` (comma separated) and, when set, `ADMIN_TOKEN`; the limits keep their defaults."""
        tokens = tuple(
            SecretStr(part.strip())
            for part in read_secret(environ, "DEMO_TOKENS").get_secret_value().split(",")
        )
        admin = read_secret(environ, "ADMIN_TOKEN") if environ.get("ADMIN_TOKEN", "").strip() else None
        return cls(
            demo_tokens=tuple(token for token in tokens if token.get_secret_value()), admin_token=admin
        )
