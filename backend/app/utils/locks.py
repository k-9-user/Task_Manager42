from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import ADMIN_INVARIANT_LOCK_KEY


def lock_admin_invariants(db: Session) -> None:
    """Serialize account bootstrap and admin-count mutations in PostgreSQL.

    The lock is transaction-scoped, so it is released by the surrounding commit
    or rollback and never leaks on an error path.
    """

    db.execute(select(func.pg_advisory_xact_lock(ADMIN_INVARIANT_LOCK_KEY)))
