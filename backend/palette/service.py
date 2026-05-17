import json
import logging
import math
from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from color.models import PhysicalColor
from color.service import lab_distance
from core.exceptions import BadRequestError, NotFoundError
from palette.models import MappedByEnum, PaletteColorMapping
from production.models import ProductionJob

logger = logging.getLogger(__name__)


async def list_copy_candidates(db: AsyncSession, job_id: UUID) -> list[dict]:
    """列出可作為「從其他 job 複製對應」來源的 job：
    - 同 batch_id 或同 image_id（admin_color.md §2.2）
    - 已有完整 palette_color_mappings（每筆色號都對到 physical_color）
    - 排除自己

    回傳依 created_at desc 排序的 list[dict]，每筆已含 filled signed URL。
    """
    from sqlalchemy import and_, func, or_

    from production.service import _make_signed_url

    target = await _get_job_or_404(db, job_id)

    if target.batch_id is None and target.image_id is None:
        return []

    # 撈同批次或同原圖的其他 job
    conditions = []
    if target.batch_id is not None:
        conditions.append(ProductionJob.batch_id == target.batch_id)
    if target.image_id is not None:
        conditions.append(ProductionJob.image_id == target.image_id)
    related = (
        await db.execute(
            select(ProductionJob).where(
                and_(
                    or_(*conditions),
                    ProductionJob.id != target.id,
                    ProductionJob.status == "completed",
                )
            ).order_by(ProductionJob.created_at.desc())
        )
    ).scalars().all()

    # 過濾出有完整 mapping 的 job（mapping 數 >= palette_json 長度）
    items = []
    for j in related:
        if not j.palette_json:
            continue
        cnt = (
            await db.execute(
                select(func.count(PaletteColorMapping.id)).where(
                    PaletteColorMapping.production_job_id == j.id
                )
            )
        ).scalar()
        if cnt < len(j.palette_json):
            continue
        relation = (
            "same_batch"
            if j.batch_id is not None and j.batch_id == target.batch_id
            else "same_image"
        )
        items.append({
            "job_id": j.id,
            "detail": str(j.detail),
            "difficulty": str(j.difficulty),
            "canvas_w_cm": float(j.canvas_w_cm),
            "canvas_h_cm": float(j.canvas_h_cm),
            "num_colors_used": j.num_colors_used,
            "filled_template_url": (
                _make_signed_url(j.filled_template_url) if j.filled_template_url else None
            ),
            "relation": relation,
            "created_at": j.created_at,
        })
    return items


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

    # 對應完成後產出「實體色版最終模板」：重編號 + 上傳 template_final.svg
    # + palette_final.json。失敗只 log 不擋使用者完成流程（Firebase / SVG
    # 解析異常時，PDF 匯出會 fallback 回原始 template.svg）。
    try:
        await finalize_template(db, job_id)
    except Exception as e:  # noqa: BLE001
        logger.warning("finalize_template failed for %s (best-effort): %s", job_id, e)

    return {
        "all_stocked": len(shortage_colors) == 0,
        "shortage_colors": shortage_colors,
    }


async def finalize_template(db: AsyncSession, job_id: UUID) -> dict:
    """產出「實體色版最終模板」：

    1. 依 palette_json.pixels 統計每個 template_id 的塗色面積
    2. 按 physical_color_id groupby，組內總 pixels 加總當排序鍵
    3. 由大到小派 output_label = 1..N，回寫每個 mapping 的 output_label
    4. 從 Firebase 拉 template.svg → renumber_svg_labels → 上傳 template_final.svg
    5. 組 palette_final.json（legend 資料源）→ 上傳
    6. 更新 job.template_final_url / palette_final_url / finalized_at

    呼叫端：complete_mappings 完成 required_ml 計算後自動觸發。冪等。

    回傳：{"output_labels_count": N, "template_final_url": ..., "palette_final_url": ...}
    """
    from core.firebase import get_bucket  # noqa: PLC0415

    from palette.svg_consolidate import regenerate_merged_svg  # noqa: PLC0415

    job = await _get_job_or_404(db, job_id)

    if not job.svg_url:
        raise BadRequestError("job 尚無 template.svg URL，無法 finalize")
    if not job.palette_json:
        raise BadRequestError("job 尚無 palette_json，無法統計面積")

    mapping_rows = list(
        (
            await db.execute(
                select(PaletteColorMapping).where(
                    PaletteColorMapping.production_job_id == job_id
                )
            )
        ).scalars().all()
    )
    if not mapping_rows:
        raise BadRequestError("尚無調色板對應資料，無法 finalize")

    # 1. template_id → pixels (來自 pbn_gen 的 palette_json，必有 pixels 欄位)
    pixels_by_template: dict[int, int] = {}
    for entry in job.palette_json:
        pixels_by_template[int(entry["template_id"])] = int(entry.get("pixels", 0))

    # 2. groupby physical_color_id，組內 pixels 加總
    groups: dict[UUID, list[PaletteColorMapping]] = defaultdict(list)
    for m in mapping_rows:
        groups[m.physical_color_id].append(m)

    def group_area(pc_id: UUID) -> int:
        return sum(pixels_by_template.get(m.template_id, 0) for m in groups[pc_id])

    # 3. 排序+派 label。同面積時用 physical_color_id 字典序破 tie 保證 deterministic
    sorted_pc_ids = sorted(
        groups.keys(),
        key=lambda pc_id: (-group_area(pc_id), str(pc_id)),
    )

    label_map: dict[int, int] = {}   # template_id → output_label
    for new_label, pc_id in enumerate(sorted_pc_ids, start=1):
        for m in groups[pc_id]:
            m.output_label = new_label
            label_map[m.template_id] = new_label

    # 4. 先建 palette_final（後面 SVG 合併要用它取得實體色 RGB 算新 tint）
    colors_by_id = {
        c.id: c
        for c in (
            await db.execute(
                select(PhysicalColor).where(
                    PhysicalColor.id.in_(list(groups.keys()))
                )
            )
        ).scalars().all()
    }

    palette_final = []
    for new_label, pc_id in enumerate(sorted_pc_ids, start=1):
        members = groups[pc_id]
        color = colors_by_id.get(pc_id)
        total_pixels = sum(pixels_by_template.get(m.template_id, 0) for m in members)
        total_ml = sum(float(m.required_ml or 0) for m in members)
        rgb = list(color.rgb) if color else [0, 0, 0]
        palette_final.append({
            "output_label": new_label,
            "physical_color_id": str(pc_id),
            "code": color.code if color else "?",
            "name": color.name if color else "?",
            "rgb": rgb,
            "hex": "#{:02X}{:02X}{:02X}".format(*rgb),
            "total_pixels": total_pixels,
            "total_ml": round(total_ml, 2),
            "member_template_ids": sorted(m.template_id for m in members),
        })

    # 5. SVG 合併 — 拉 template.svg → 同 output_label 的多邊形 Shapely union
    #    → 渲染為新 SVG（消除同色相鄰假邊界）→ 上傳 final
    bucket = get_bucket()
    svg_path = _gs_path(job.svg_url, bucket.name)
    svg_blob = bucket.blob(svg_path)
    svg_bytes = svg_blob.download_as_bytes()
    final_svg_bytes = regenerate_merged_svg(
        svg_bytes, label_map, job.palette_json, palette_final,
    )

    final_svg_path = f"production_jobs/{job_id}/template_final.svg"
    bucket.blob(final_svg_path).upload_from_string(
        final_svg_bytes, content_type="image/svg+xml",
    )
    template_final_url = f"gs://{bucket.name}/{final_svg_path}"

    # 6. 上傳 palette_final.json（legend 用）
    palette_final_path = f"production_jobs/{job_id}/palette_final.json"
    bucket.blob(palette_final_path).upload_from_string(
        json.dumps(palette_final, ensure_ascii=False, indent=2),
        content_type="application/json",
    )
    palette_final_url = f"gs://{bucket.name}/{palette_final_path}"

    # 7. 生成「實體色版」filled preview（pixel-replacement）— 若 snapped_rgb 存在
    # snapped_rgb.png 是 pbn_gen 量化後的 raw RGB 圖（每個 pixel 是某個 algorithm
    # template_id 的色）。把每個 algorithm RGB 換成對應物理色 RGB → 真實塗色預覽。
    filled_template_final_url: str | None = None
    if job.snapped_rgb_url:
        try:
            filled_template_final_url = await _generate_filled_final(
                bucket, job, mapping_rows, colors_by_id,
            )
        except Exception as e:  # noqa: BLE001
            # best-effort：失敗只 log，其他 finalize 產物仍生效
            logger.warning(
                "filled_template_final generation failed for %s: %s", job_id, e,
            )

    # 8. 更新 job 欄位 + commit
    job.template_final_url = template_final_url
    job.palette_final_url = palette_final_url
    if filled_template_final_url:
        job.filled_template_final_url = filled_template_final_url
    job.finalized_at = datetime.now(UTC)
    await db.commit()

    logger.info(
        "finalize_template: job=%s mappings=%d unique_colors=%d",
        job_id, len(mapping_rows), len(sorted_pc_ids),
    )
    return {
        "output_labels_count": len(sorted_pc_ids),
        "template_final_url": template_final_url,
        "palette_final_url": palette_final_url,
    }


async def _generate_filled_final(
    bucket,
    job: ProductionJob,
    mapping_rows: list[PaletteColorMapping],
    colors_by_id: dict[UUID, PhysicalColor],
) -> str:
    """以 snapped_rgb.png 為基底，把每個 algorithm RGB pixel 換成對應物理色 RGB。

    回傳 Firebase gs:// URL；失敗會 raise，呼叫端用 try/except 視為 best-effort。

    向量化作法（O(num_colors × pixels)，但 num_colors 通常 ≤ 50 所以實際很快）：
      1. 讀 snapped_rgb 成 numpy (H, W, 3) uint8
      2. 對每個 mapping，組 algorithm RGB → physical RGB 的對應
      3. 用 np.all(img == alg, axis=-1) 找該色 pixel mask，整批替換
    """
    import io  # noqa: PLC0415

    import numpy as np  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415

    # 1. 讀 snapped_rgb
    snapped_path = _gs_path(job.snapped_rgb_url, bucket.name)
    snapped_bytes = bucket.blob(snapped_path).download_as_bytes()
    snapped_img = np.array(
        Image.open(io.BytesIO(snapped_bytes)).convert("RGB"),
        dtype=np.uint8,
    )

    # 2. 組 algorithm RGB tuple → physical RGB tuple
    # palette_json 的 rgb 是 algorithm 量化色（與 snapped_rgb pixel 對齊）；
    # mapping_rows 的 algorithm_rgb 也是同來源
    alg_to_phys: dict[tuple[int, int, int], tuple[int, int, int]] = {}
    for m in mapping_rows:
        color = colors_by_id.get(m.physical_color_id)
        if not color:
            continue
        alg_rgb = m.algorithm_rgb
        if isinstance(alg_rgb, dict):
            alg_t = (int(alg_rgb["r"]), int(alg_rgb["g"]), int(alg_rgb["b"]))
        else:
            alg_t = (int(alg_rgb[0]), int(alg_rgb[1]), int(alg_rgb[2]))
        phys_t = (int(color.rgb[0]), int(color.rgb[1]), int(color.rgb[2]))
        alg_to_phys[alg_t] = phys_t

    if not alg_to_phys:
        raise ValueError("mapping_rows 內無有效 algorithm→physical 對應")

    # 3. 整批替換像素
    output = snapped_img.copy()
    for alg, phys in alg_to_phys.items():
        if alg == phys:
            continue  # 已相同，省略一次掃描
        mask = np.all(snapped_img == np.array(alg, dtype=np.uint8), axis=-1)
        output[mask] = phys

    # 4. 編碼 PNG → 上傳
    buf = io.BytesIO()
    Image.fromarray(output, mode="RGB").save(buf, format="PNG", optimize=True)
    filled_bytes = buf.getvalue()

    filled_path = f"production_jobs/{job.id}/filled_template_final.png"
    bucket.blob(filled_path).upload_from_string(
        filled_bytes, content_type="image/png",
    )
    return f"gs://{bucket.name}/{filled_path}"


def _gs_path(url: str, bucket_name: str) -> str:
    """從 gs://bucket/path 萃出 path（不含 bucket）；非 gs:// 直接回 url。"""
    prefix = f"gs://{bucket_name}/"
    if url.startswith(prefix):
        return url[len(prefix):]
    if url.startswith("gs://"):
        # 萬一 bucket name 不同（測試環境），仍盡力解析
        return url.split("/", 3)[-1]
    return url


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
            "output_label": m.output_label,
        })
    return enriched


async def _get_settings(db: AsyncSession) -> dict[str, str]:
    from color.models import SystemSetting
    result = await db.execute(select(SystemSetting))
    return {s.key: s.value for s in result.scalars().all()}
