import math
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from color.models import PhysicalColor
from color.service import lab_distance
from core.exceptions import BadRequestError, NotFoundError
from palette.models import MappedByEnum, PaletteColorMapping
from production.models import ProductionJob


async def get_mappings(db: AsyncSession, job_id: UUID) -> list[dict]:
    job = await _get_job_or_404(db, job_id)

    result = await db.execute(
        select(PaletteColorMapping).where(
            PaletteColorMapping.production_job_id == job_id
        )
    )
    mappings = list(result.scalars().all())

    if not mappings:
        if not job.palette_json:
            return []
        mappings = await _auto_map(db, job)

    return await _enrich_mappings(db, mappings)


async def update_mapping(
    db: AsyncSession, job_id: UUID, template_id: int, physical_color_id: UUID
) -> dict:
    await _get_job_or_404(db, job_id)

    color = await db.execute(
        select(PhysicalColor).where(
            PhysicalColor.id == physical_color_id,
            PhysicalColor.is_active == True,  # noqa: E712
        )
    )
    if not color.scalar_one_or_none():
        raise NotFoundError("實體色不存在或已停用")

    result = await db.execute(
        select(PaletteColorMapping).where(
            PaletteColorMapping.production_job_id == job_id,
            PaletteColorMapping.template_id == template_id,
        )
    )
    mapping = result.scalar_one_or_none()
    if not mapping:
        raise NotFoundError("調色板對應不存在")

    mapping.physical_color_id = physical_color_id
    mapping.mapped_by = MappedByEnum.manual
    mapping.required_ml = None
    await db.commit()
    await db.refresh(mapping)

    enriched = await _enrich_mappings(db, [mapping])
    return enriched[0]


async def copy_from_job(
    db: AsyncSession, job_id: UUID, source_job_id: UUID
) -> list[dict]:
    if job_id == source_job_id:
        raise BadRequestError("不能從自身複製調色板對應")
    await _get_job_or_404(db, job_id)
    await _get_job_or_404(db, source_job_id)

    source_result = await db.execute(
        select(PaletteColorMapping).where(
            PaletteColorMapping.production_job_id == source_job_id
        )
    )
    source_mappings = list(source_result.scalars().all())
    if not source_mappings:
        raise BadRequestError("來源 job 沒有調色板對應資料")

    source_by_template = {m.template_id: m for m in source_mappings}

    source_color_ids = list({m.physical_color_id for m in source_mappings})
    active_result = await db.execute(
        select(PhysicalColor).where(
            PhysicalColor.id.in_(source_color_ids),
            PhysicalColor.is_active == True,  # noqa: E712
        )
    )
    active_color_ids = {c.id for c in active_result.scalars().all()}
    missing = [
        tid for tid, m in source_by_template.items()
        if m.physical_color_id not in active_color_ids
    ]
    if missing:
        raise BadRequestError(
            f"來源 job 部分對應色彩已停用或不存在，無法複製（template_id: {missing}）"
        )

    existing_result = await db.execute(
        select(PaletteColorMapping).where(
            PaletteColorMapping.production_job_id == job_id
        )
    )
    existing = {m.template_id: m for m in existing_result.scalars().all()}

    for template_id, src in source_by_template.items():
        if template_id in existing:
            existing[template_id].physical_color_id = src.physical_color_id
            existing[template_id].mapped_by = MappedByEnum.manual
            existing[template_id].required_ml = None
        else:
            new_mapping = PaletteColorMapping(
                production_job_id=job_id,
                template_id=template_id,
                algorithm_rgb=src.algorithm_rgb,
                physical_color_id=src.physical_color_id,
                mapped_by=MappedByEnum.manual,
                required_ml=None,
            )
            db.add(new_mapping)

    await db.commit()

    result = await db.execute(
        select(PaletteColorMapping).where(
            PaletteColorMapping.production_job_id == job_id
        )
    )
    mappings = list(result.scalars().all())
    return await _enrich_mappings(db, mappings)


async def complete_mappings(db: AsyncSession, job_id: UUID) -> dict:
    job = await _get_job_or_404(db, job_id)

    result = await db.execute(
        select(PaletteColorMapping).where(
            PaletteColorMapping.production_job_id == job_id
        )
    )
    mappings = list(result.scalars().all())

    if not mappings:
        raise BadRequestError("尚無調色板對應資料")

    if job.palette_json:
        palette_ids = {entry["template_id"] for entry in job.palette_json}
        mapped_ids = {m.template_id for m in mappings}
        if palette_ids - mapped_ids:
            raise BadRequestError("尚有未對應的色號，無法完成")

    settings = await _get_settings(db)
    paint_ml_per_cm2 = float(settings.get("paint_ml_per_cm2", "0.05"))
    paint_min_ml = float(settings.get("paint_min_ml", "3.0"))
    paint_buffer_ratio = float(settings.get("paint_buffer_ratio", "1.3"))

    area = float(job.canvas_w_cm) * float(job.canvas_h_cm)

    palette_by_id: dict[int, dict] = {}
    if job.palette_json:
        for entry in job.palette_json:
            palette_by_id[entry["template_id"]] = entry

    color_ids = [m.physical_color_id for m in mappings]
    colors_result = await db.execute(
        select(PhysicalColor).where(PhysicalColor.id.in_(color_ids))
    )
    colors_by_id = {c.id: c for c in colors_result.scalars().all()}

    shortage_colors = []
    for mapping in mappings:
        entry = palette_by_id.get(mapping.template_id, {})
        percent = float(entry.get("percent", 0.0))
        required = max(
            area * percent * paint_ml_per_cm2 * paint_buffer_ratio,
            paint_min_ml,
        )
        required = math.ceil(required * 100) / 100
        mapping.required_ml = required

        color = colors_by_id.get(mapping.physical_color_id)
        if color and float(color.stock_ml) < required:
            shortage_colors.append({
                "template_id": mapping.template_id,
                "physical_color_id": mapping.physical_color_id,
                "code": color.code,
                "name": color.name,
            })

    await db.commit()

    return {
        "all_stocked": len(shortage_colors) == 0,
        "shortage_colors": shortage_colors,
    }


# ── helpers ──────────────────────────────────────────────────────────────────

async def _get_job_or_404(db: AsyncSession, job_id: UUID) -> ProductionJob:
    result = await db.execute(
        select(ProductionJob).where(ProductionJob.id == job_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise NotFoundError("生產工作不存在")
    return job


async def _auto_map(
    db: AsyncSession, job: ProductionJob
) -> list[PaletteColorMapping]:
    colors_result = await db.execute(
        select(PhysicalColor).where(PhysicalColor.is_active == True)  # noqa: E712
    )
    active_colors = list(colors_result.scalars().all())

    in_stock = [c for c in active_colors if float(c.stock_ml) > 0]
    # Global preference: use in-stock pool for all templates if any exist;
    # fall back to full active pool only when nothing is in stock.
    candidates = in_stock if in_stock else active_colors

    if not candidates:
        raise BadRequestError("尚無可用的實體色，無法自動對應")

    new_mappings = []
    for entry in job.palette_json:
        template_id = entry["template_id"]
        rgb = entry["rgb"]
        # palette_json.rgb 為 list[int] 三元組 [r, g, b]（schema.md 規範）
        # 兼容極舊資料格式 {"r":..., "g":..., "b":...}（早期版本，正常情況不會出現）
        if isinstance(rgb, dict):
            alg_rgb = [int(rgb["r"]), int(rgb["g"]), int(rgb["b"])]
        else:
            alg_rgb = [int(c) for c in rgb]

        best = min(
            candidates,
            key=lambda c, _rgb=alg_rgb: (
                lab_distance(_rgb, c.rgb),
                str(c.id),
            ),
        )

        mapping = PaletteColorMapping(
            production_job_id=job.id,
            template_id=template_id,
            algorithm_rgb=alg_rgb,
            physical_color_id=best.id,
            mapped_by=MappedByEnum.system,
        )
        db.add(mapping)
        new_mappings.append(mapping)

    try:
        await db.commit()
    except IntegrityError:
        # Concurrent request already created mappings for this job; use those.
        await db.rollback()
        result = await db.execute(
            select(PaletteColorMapping).where(
                PaletteColorMapping.production_job_id == job.id
            )
        )
        return list(result.scalars().all())

    for m in new_mappings:
        await db.refresh(m)
    return new_mappings


async def _enrich_mappings(
    db: AsyncSession, mappings: list[PaletteColorMapping]
) -> list[dict]:
    color_ids = [m.physical_color_id for m in mappings]
    colors_result = await db.execute(
        select(PhysicalColor).where(PhysicalColor.id.in_(color_ids))
    )
    colors_by_id = {c.id: c for c in colors_result.scalars().all()}

    enriched = []
    for m in mappings:
        color = colors_by_id.get(m.physical_color_id)
        enriched.append({
            "template_id": m.template_id,
            "algorithm_rgb": list(m.algorithm_rgb),
            "physical_color": {
                "id": color.id,
                "code": color.code,
                "name": color.name,
                "rgb": color.rgb,
                "stock_ml": float(color.stock_ml),
            } if color else None,
            "required_ml": float(m.required_ml) if m.required_ml is not None else None,
            "mapped_by": m.mapped_by,
        })
    return enriched


async def _get_settings(db: AsyncSession) -> dict[str, str]:
    from color.models import SystemSetting
    result = await db.execute(select(SystemSetting))
    return {s.key: s.value for s in result.scalars().all()}
