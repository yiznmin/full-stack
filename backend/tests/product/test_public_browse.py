"""Module 12 — public store browse tests."""

import pytest
from sqlalchemy import select

from product.models import (
    Product,
    ProductImage,
    ProductSeries,
    ProductStatusEnum,
    ProductTag,
    ProductVariant,
    Tag,
)
from production.models import ProductionJob

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _make_job(db, *, w=30, h=40, difficulty="beginner", detail="standard", colors=18):
    job = ProductionJob(
        detail=detail,
        difficulty=difficulty,
        canvas_w_cm=w,
        canvas_h_cm=h,
        num_colors_used=colors,
        approved=True,
        status="completed",
        filled_template_url="http://example.com/filled.png",
    )
    db.add(job)
    await db.flush()
    return job


async def _make_product(
    db, *, title="畫", status=ProductStatusEnum.on_sale,
    series_id=None, series_order=None,
):
    p = Product(
        title=title,
        description=f"{title} 描述",
        cover_image_url="http://example.com/cover.png",
        status=status,
        series_id=series_id,
        series_order=series_order,
    )
    db.add(p)
    await db.flush()
    return p


async def _make_variant(db, product_id, job_id, *, price=500, is_active=True):
    v = ProductVariant(
        product_id=product_id,
        production_job_id=job_id,
        price=price,
        price_formula_base=price,
        is_active=is_active,
    )
    db.add(v)
    await db.flush()
    return v


async def _seed_basic(db):
    job1 = await _make_job(db, w=30, h=40, difficulty="beginner")
    p1 = await _make_product(db, title="湖光山色")
    await _make_variant(db, p1.id, job1.id, price=500)
    await db.commit()
    return p1, job1


# ── List ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_default(client, db):
    await _seed_basic(db)
    res = await client.get("/api/v1/products")
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["title"] == "湖光山色"
    assert item["price_min"] == 500.0
    assert item["price_max"] == 500.0
    assert item["difficulty_range"] == ["beginner", "beginner"]


@pytest.mark.asyncio
async def test_list_excludes_draft(client, db):
    job = await _make_job(db)
    draft = await _make_product(db, title="尚未上架", status=ProductStatusEnum.draft)
    await _make_variant(db, draft.id, job.id)
    on_sale = await _make_product(db, title="已上架")
    job2 = await _make_job(db)
    await _make_variant(db, on_sale.id, job2.id)
    await db.commit()

    res = await client.get("/api/v1/products")
    assert res.status_code == 200
    titles = [i["title"] for i in res.json()["items"]]
    assert "已上架" in titles
    assert "尚未上架" not in titles


@pytest.mark.asyncio
async def test_list_filter_difficulty(client, db):
    j1 = await _make_job(db, difficulty="beginner")
    j2 = await _make_job(db, difficulty="advanced")
    p1 = await _make_product(db, title="入門")
    p2 = await _make_product(db, title="高難")
    await _make_variant(db, p1.id, j1.id)
    await _make_variant(db, p2.id, j2.id)
    await db.commit()

    res = await client.get("/api/v1/products?difficulty=advanced")
    titles = [i["title"] for i in res.json()["items"]]
    assert titles == ["高難"]


@pytest.mark.asyncio
async def test_list_filter_canvas_size(client, db):
    j_a = await _make_job(db, w=30, h=40)
    j_b = await _make_job(db, w=50, h=50)
    pa = await _make_product(db, title="3040")
    pb = await _make_product(db, title="5050")
    await _make_variant(db, pa.id, j_a.id)
    await _make_variant(db, pb.id, j_b.id)
    await db.commit()

    res = await client.get("/api/v1/products?canvas_size=30x40")
    titles = [i["title"] for i in res.json()["items"]]
    assert titles == ["3040"]


@pytest.mark.asyncio
async def test_list_filter_tag(client, db):
    tag = Tag(name="風景")
    db.add(tag)
    await db.flush()
    job = await _make_job(db)
    p1 = await _make_product(db, title="風景畫")
    p2 = await _make_product(db, title="人像")
    await _make_variant(db, p1.id, job.id)
    j2 = await _make_job(db)
    await _make_variant(db, p2.id, j2.id)
    db.add(ProductTag(product_id=p1.id, tag_id=tag.id))
    await db.commit()

    res = await client.get(f"/api/v1/products?tag_id={tag.id}")
    titles = [i["title"] for i in res.json()["items"]]
    assert titles == ["風景畫"]


@pytest.mark.asyncio
async def test_list_sort_price(client, db):
    j1 = await _make_job(db)
    j2 = await _make_job(db)
    p_cheap = await _make_product(db, title="便宜")
    p_pricey = await _make_product(db, title="昂貴")
    await _make_variant(db, p_cheap.id, j1.id, price=300)
    await _make_variant(db, p_pricey.id, j2.id, price=900)
    await db.commit()

    res = await client.get("/api/v1/products?sort=price_asc")
    titles = [i["title"] for i in res.json()["items"]]
    assert titles == ["便宜", "昂貴"]

    res = await client.get("/api/v1/products?sort=price_desc")
    titles = [i["title"] for i in res.json()["items"]]
    assert titles == ["昂貴", "便宜"]


@pytest.mark.asyncio
async def test_list_sort_latest(client, db):
    j1 = await _make_job(db)
    j2 = await _make_job(db)
    p_old = await _make_product(db, title="舊")
    await _make_variant(db, p_old.id, j1.id)
    await db.commit()
    p_new = await _make_product(db, title="新")
    await _make_variant(db, p_new.id, j2.id)
    await db.commit()

    res = await client.get("/api/v1/products?sort=latest")
    titles = [i["title"] for i in res.json()["items"]]
    assert titles[0] == "新"


@pytest.mark.asyncio
async def test_list_pagination(client, db):
    for i in range(5):
        j = await _make_job(db)
        p = await _make_product(db, title=f"P{i}")
        await _make_variant(db, p.id, j.id)
    await db.commit()

    res = await client.get("/api/v1/products?page=1&page_size=2")
    body = res.json()
    assert body["total"] == 5
    assert body["page"] == 1
    assert body["page_size"] == 2
    assert len(body["items"]) == 2


# ── Search ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_returns_match(client, db):
    j = await _make_job(db)
    p = await _make_product(db, title="向日葵")
    await _make_variant(db, p.id, j.id)
    await db.commit()
    res = await client.get("/api/v1/products/search?q=向日")
    assert res.status_code == 200
    titles = [i["title"] for i in res.json()["items"]]
    assert "向日葵" in titles


# ── Detail ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_detail_on_sale(client, db):
    j = await _make_job(db, w=30, h=40, difficulty="beginner", detail="standard", colors=18)
    p = await _make_product(db, title="細節商品")
    await _make_variant(db, p.id, j.id, price=500)
    await db.commit()

    res = await client.get(f"/api/v1/products/{p.id}")
    assert res.status_code == 200
    body = res.json()
    assert body["title"] == "細節商品"
    assert len(body["variants"]) == 1
    v = body["variants"][0]
    assert v["canvas_w_cm"] == 30.0
    assert v["color_count"] == 18
    assert v["price"] == 500.0


@pytest.mark.asyncio
async def test_detail_draft_404(client, db):
    j = await _make_job(db)
    p = await _make_product(db, title="草稿", status=ProductStatusEnum.draft)
    await _make_variant(db, p.id, j.id)
    await db.commit()
    res = await client.get(f"/api/v1/products/{p.id}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_detail_hides_inactive_variants(client, db):
    j1 = await _make_job(db)
    j2 = await _make_job(db)
    p = await _make_product(db, title="混合")
    await _make_variant(db, p.id, j1.id, is_active=True)
    await _make_variant(db, p.id, j2.id, is_active=False)
    await db.commit()

    res = await client.get(f"/api/v1/products/{p.id}")
    body = res.json()
    assert len(body["variants"]) == 1
    assert body["variants"][0]["is_active"] is True


# ── Related ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_related_in_series(client, db):
    series = ProductSeries(name="春日系列")
    db.add(series)
    await db.flush()
    j1 = await _make_job(db)
    j2 = await _make_job(db)
    j3 = await _make_job(db)
    p1 = await _make_product(db, title="A", series_id=series.id, series_order=1)
    p2 = await _make_product(db, title="B", series_id=series.id, series_order=2)
    p3 = await _make_product(db, title="C", series_id=series.id, series_order=3)
    await _make_variant(db, p1.id, j1.id)
    await _make_variant(db, p2.id, j2.id)
    await _make_variant(db, p3.id, j3.id)
    await db.commit()

    res = await client.get(f"/api/v1/products/{p2.id}/related")
    body = res.json()
    assert body["series"]["name"] == "春日系列"
    titles = [i["title"] for i in body["items"]]
    assert "B" not in titles
    assert titles == ["A", "C"]


@pytest.mark.asyncio
async def test_related_no_series(client, db):
    j = await _make_job(db)
    p = await _make_product(db, title="獨立")
    await _make_variant(db, p.id, j.id)
    await db.commit()

    res = await client.get(f"/api/v1/products/{p.id}/related")
    body = res.json()
    assert body["series"] is None
    assert body["items"] == []


# ── Path collision / zombie filter ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_path_does_not_match_id_route(client, db):
    """GET /products/search must hit the search endpoint, not /products/{id}.

    FastAPI route order matters; this is a regression guard.
    """
    res = await client.get("/api/v1/products/search?q=x")
    # Even with no products, this should be 200 (empty list), not 404 / 422 from UUID parsing
    assert res.status_code == 200
    body = res.json()
    assert "items" in body and "total" in body


@pytest.mark.asyncio
async def test_list_excludes_products_without_active_variants(client, db):
    """A product whose variants are all inactive should NOT appear in list."""
    job = await _make_job(db)
    p_zombie = await _make_product(db, title="只有 inactive variant")
    await _make_variant(db, p_zombie.id, job.id, is_active=False)
    p_ok = await _make_product(db, title="正常上架")
    job2 = await _make_job(db)
    await _make_variant(db, p_ok.id, job2.id, is_active=True)
    await db.commit()
    res = await client.get("/api/v1/products")
    titles = [i["title"] for i in res.json()["items"]]
    assert "只有 inactive variant" not in titles
    assert "正常上架" in titles


@pytest.mark.asyncio
async def test_search_excludes_inactive_only_products(client, db):
    job = await _make_job(db)
    p = await _make_product(db, title="獨家秘藏")
    await _make_variant(db, p.id, job.id, is_active=False)
    await db.commit()
    res = await client.get("/api/v1/products/search?q=秘藏")
    titles = [i["title"] for i in res.json()["items"]]
    assert "獨家秘藏" not in titles


# ── Tags ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_public_tags(client, db):
    db.add(Tag(name="風景"))
    db.add(Tag(name="動物"))
    await db.commit()
    res = await client.get("/api/v1/tags")
    body = res.json()
    names = [t["name"] for t in body["items"]]
    assert "風景" in names
    assert "動物" in names
    # public response should NOT include product_count
    assert "product_count" not in body["items"][0]


# Suppress unused-import warning
_ = (ProductImage, select)
