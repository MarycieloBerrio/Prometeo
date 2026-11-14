"""TrialRepository backed by Postgres/Supabase (schema: infra/db/migrations).

Not wired yet — the MVP uses `JsonTrialRepository`. Implement the three methods with psycopg,
map rows -> domain objects here (never leak rows past this module), then switch
`PROMETEO_TRIAL_STORE=postgres` in the composition root.
"""

from __future__ import annotations

from prometeo.domain.experiments.filters import TrialFilter
from prometeo.domain.experiments.model import Trial


class PostgresTrialRepository:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn

    def get(self, trial_id: str) -> Trial | None:
        raise NotImplementedError("TODO: SELECT trial + measurements + media by id")

    def search(self, criteria: TrialFilter) -> list[Trial]:
        raise NotImplementedError("TODO: translate TrialFilter into a parameterized query")

    def list_all(self) -> list[Trial]:
        raise NotImplementedError
