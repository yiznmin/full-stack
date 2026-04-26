"""seed 270 physical colors from CSV

Revision ID: h8c9d0e1f2g3
Revises: g7b8c9d0e1f2
Create Date: 2026-04-26 04:00:00.000000

"""
import csv
import uuid
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision: str = 'h8c9d0e1f2g3'
down_revision: str | Sequence[str] | None = 'g7b8c9d0e1f2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_CSV_PATH = Path(__file__).parent / "seed_data" / "physical_colors_seed.csv"


def _load_seed_rows() -> list[dict]:
    rows: list[dict] = []
    with open(_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({
                "code": r["code"].strip(),
                "name": r["name"].strip(),
                "color_family": (r["color_family"].strip() or None) if r.get("color_family") else None,
                "brand": (r["brand"].strip() or None) if r.get("brand") else None,
                "rgb": [int(r["rgb_r"]), int(r["rgb_g"]), int(r["rgb_b"])],
                "stock_ml": float(r["stock_ml"] or 0),
                "is_active": str(r["is_active"]).strip().lower() == "true",
            })
    return rows


def upgrade() -> None:
    physical_colors_t = sa.Table(
        "physical_colors",
        sa.MetaData(),
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True)),
        sa.Column("code", sa.String()),
        sa.Column("name", sa.String()),
        sa.Column("color_family", sa.String()),
        sa.Column("brand", sa.String()),
        sa.Column("rgb", sa.dialects.postgresql.JSONB()),
        sa.Column("stock_ml", sa.Numeric(10, 2)),
        sa.Column("is_active", sa.Boolean()),
    )
    history_t = sa.Table(
        "physical_color_rgb_history",
        sa.MetaData(),
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True)),
        sa.Column("physical_color_id", sa.dialects.postgresql.UUID(as_uuid=True)),
        sa.Column("rgb", sa.dialects.postgresql.JSONB()),
        sa.Column("changed_by_user_id", sa.dialects.postgresql.UUID(as_uuid=True)),
        sa.Column("note", sa.String()),
    )

    seed_rows = _load_seed_rows()
    color_records: list[dict] = []
    history_records: list[dict] = []
    for r in seed_rows:
        cid = uuid.uuid4()
        color_records.append({
            "id": cid,
            "code": r["code"],
            "name": r["name"],
            "color_family": r["color_family"],
            "brand": r["brand"],
            "rgb": r["rgb"],
            "stock_ml": r["stock_ml"],
            "is_active": r["is_active"],
        })
        history_records.append({
            "id": uuid.uuid4(),
            "physical_color_id": cid,
            "rgb": r["rgb"],
            "changed_by_user_id": None,
            "note": "initial (seed)",
        })

    op.bulk_insert(physical_colors_t, color_records)
    op.bulk_insert(history_t, history_records)


def downgrade() -> None:
    seed_rows = _load_seed_rows()
    codes = [r["code"] for r in seed_rows]
    # history rows cascade-delete via FK ON DELETE CASCADE on physical_color_id
    op.execute(
        sa.text("DELETE FROM physical_colors WHERE code = ANY(:codes)").bindparams(
            sa.bindparam("codes", value=codes, type_=sa.ARRAY(sa.String))
        )
    )
