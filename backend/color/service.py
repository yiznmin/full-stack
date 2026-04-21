import math
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from color.models import PhysicalColor
from core.exceptions import ConflictError, NotFoundError


async def list_colors(
    db: AsyncSession,
    color_family: str | None,
    is_active: bool | None,
    search: str | None,
) -> list[PhysicalColor]:
    q = select(PhysicalColor)
    if color_family is not None:
        q = q.where(PhysicalColor.color_family == color_family)
    if is_active is not None:
        q = q.where(PhysicalColor.is_active == is_active)
    if search:
        pattern = f"%{search}%"
        q = q.where(
            PhysicalColor.code.ilike(pattern) | PhysicalColor.name.ilike(pattern)
        )
    q = q.order_by(PhysicalColor.code)
    result = await db.execute(q)
    return list(result.scalars().all())


async def create_color(db: AsyncSession, data: dict) -> PhysicalColor:
    existing = await db.execute(
        select(PhysicalColor).where(PhysicalColor.code == data["code"])
    )
    if existing.scalar_one_or_none():
        raise ConflictError(f"色號 {data['code']} 已存在")
    color = PhysicalColor(**data)
    db.add(color)
    await db.commit()
    await db.refresh(color)
    return color


async def update_color(db: AsyncSession, color_id: UUID, data: dict) -> PhysicalColor:
    color = await _get_or_404(db, color_id)
    dup = await db.execute(
        select(PhysicalColor).where(
            PhysicalColor.code == data["code"],
            PhysicalColor.id != color_id,
        )
    )
    if dup.scalar_one_or_none():
        raise ConflictError(f"色號 {data['code']} 已被其他色條目使用")
    for k, v in data.items():
        setattr(color, k, v)
    await db.commit()
    await db.refresh(color)
    return color


async def toggle_active(db: AsyncSession, color_id: UUID) -> PhysicalColor:
    color = await _get_or_404(db, color_id)
    color.is_active = not color.is_active
    await db.commit()
    await db.refresh(color)
    return color


async def add_stock(db: AsyncSession, color_id: UUID, add_ml: float) -> dict:
    color = await _get_or_404(db, color_id)
    color.stock_ml = float(color.stock_ml) + add_ml
    await db.commit()
    await db.refresh(color)
    # Preorder scan stub — implemented after Orders module
    return {"new_stock_ml": float(color.stock_ml), "fulfilled_orders": 0}


async def shortage_dashboard(db: AsyncSession) -> list[dict]:
    # Orders module not built yet — required_ml from palette_color_mappings only,
    # waiting_orders always 0 until Orders is implemented
    from palette.models import PaletteColorMapping

    rows = await db.execute(
        select(
            PaletteColorMapping.physical_color_id,
            func.sum(PaletteColorMapping.required_ml).label("total_required"),
        )
        .where(PaletteColorMapping.required_ml.isnot(None))
        .group_by(PaletteColorMapping.physical_color_id)
    )
    required_by_color: dict[UUID, float] = {
        row.physical_color_id: float(row.total_required) for row in rows
    }

    colors = await list_colors(db, color_family=None, is_active=True, search=None)
    items = []
    for c in colors:
        stock = float(c.stock_ml)
        required = required_by_color.get(c.id, 0.0)
        shortage = required - stock
        if shortage > 0:
            items.append({
                "color_id": c.id,
                "code": c.code,
                "name": c.name,
                "stock_ml": stock,
                "required_ml": required,
                "shortage_ml": math.ceil(shortage * 100) / 100,
                "waiting_orders": 0,
            })
    return items


async def _get_or_404(db: AsyncSession, color_id: UUID) -> PhysicalColor:
    result = await db.execute(
        select(PhysicalColor).where(PhysicalColor.id == color_id)
    )
    color = result.scalar_one_or_none()
    if not color:
        raise NotFoundError("實體色不存在")
    return color


# ── LAB color utilities ───────────────────────────────────────────────────────

def _rgb_to_lab(r: int, g: int, b: int) -> tuple[float, float, float]:
    """Convert sRGB (0-255) to CIE LAB using D65 illuminant."""
    def linearize(c: float) -> float:
        c /= 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    rl, gl, bl = linearize(r), linearize(g), linearize(b)

    # sRGB → XYZ (D65)
    x = rl * 0.4124564 + gl * 0.3575761 + bl * 0.1804375
    y = rl * 0.2126729 + gl * 0.7151522 + bl * 0.0721750
    z = rl * 0.0193339 + gl * 0.1191920 + bl * 0.9503041

    # XYZ → LAB (D65 white point)
    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    xn, yn, zn = 0.95047, 1.00000, 1.08883
    fx, fy, fz = f(x / xn), f(y / yn), f(z / zn)
    lab_l = 116 * fy - 16
    lab_a = 500 * (fx - fy)
    b_val = 200 * (fy - fz)
    return lab_l, lab_a, b_val


def lab_distance(rgb1: list[int], rgb2: list[int]) -> float:
    l1, a1, b1 = _rgb_to_lab(*rgb1)
    l2, a2, b2 = _rgb_to_lab(*rgb2)
    return math.sqrt((l1 - l2) ** 2 + (a1 - a2) ** 2 + (b1 - b2) ** 2)
