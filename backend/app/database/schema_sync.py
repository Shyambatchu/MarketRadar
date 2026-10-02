"""Additive column reconciliation for an existing SQLite database.

``Base.metadata.create_all()`` creates missing *tables* but never alters an
existing one, and this project has no migration tool. So a column added to a
model that already has a table on disk simply does not exist, and the first
query touching it fails with "no such column".

This adds only what is missing, and only ever adds:

* no column is dropped, renamed or retyped
* no table is dropped or recreated
* no row is written, updated or deleted

Anything beyond adding a nullable column -- a type change, a new constraint, a
backfill -- is out of scope here and needs a real migration. This exists so the
development database keeps working as models grow, not as a substitute for one.
"""
import logging
from typing import Dict, Iterable, List

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger("schema_sync")

# SQLite accepts a plain type name in ADD COLUMN; these cover what the models
# use. Anything else is skipped rather than guessed at.
_SUPPORTED_TYPES = ("INTEGER", "VARCHAR", "TEXT", "FLOAT", "BOOLEAN",
                    "DATETIME", "NUMERIC")


def _addable_columns(table, existing: Iterable[str]) -> List:
    existing = set(existing)
    out = []
    for column in table.columns:
        if column.name in existing:
            continue
        # A NOT NULL column with no default cannot be added to a table that
        # may already hold rows; that needs a real migration.
        if not column.nullable and column.default is None and \
                column.server_default is None and not column.primary_key:
            logger.warning("skipping non-nullable column %s.%s: needs a migration",
                           table.name, column.name)
            continue
        out.append(column)
    return out


def sync_additive_columns(engine: Engine, metadata) -> Dict[str, List[str]]:
    """Add columns present in ``metadata`` but missing on disk.

    Returns {table: [columns added]}, empty when nothing was needed.
    """
    if not engine.url.get_backend_name().startswith("sqlite"):
        # Other backends belong to a real migration tool, not to this.
        return {}

    inspector = inspect(engine)
    present = set(inspector.get_table_names())
    added: Dict[str, List[str]] = {}

    for table in metadata.sorted_tables:
        if table.name not in present:
            continue  # create_all handles a table that does not exist yet.

        existing = [c["name"] for c in inspector.get_columns(table.name)]
        for column in _addable_columns(table, existing):
            type_sql = column.type.compile(dialect=engine.dialect).upper()
            if not any(type_sql.startswith(t) for t in _SUPPORTED_TYPES):
                logger.warning("skipping column %s.%s: unsupported type %s",
                               table.name, column.name, type_sql)
                continue

            statement = 'ALTER TABLE "%s" ADD COLUMN "%s" %s' % (
                table.name, column.name, type_sql)
            with engine.begin() as connection:
                connection.execute(text(statement))
            added.setdefault(table.name, []).append(column.name)
            logger.info("added column %s.%s", table.name, column.name)

    return added
