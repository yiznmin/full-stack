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
async def test_detail_converts_gs_filled_url_to_signed_https(client, db):
    """Regression：production_jobs.filled_template_url 改 gs:// 後，公開 endpoint 必須回 https
    （瀏覽器無法載 gs://）。Phase 2-A integration 後新增。"""
    from unittest.mock import patch

    j = await _make_job(db, w=30, h=40)
    # 直接覆寫成 gs:// 模擬新引擎輸出
    j.filled_template_url = "gs://test-bucket/production_jobs/abc/filled.png"
    p = await _make_product(db, title="gs URL 商品")
    await _make_variant(db, p.id, j.id, price=600)
    await db.commit()

    with patch(
        "production.service._make_signed_url",
        return_value="https://storage.googleapis.com/test-bucket/.../signed?token=x",
    ):
        res = await client.get(f"/api/v1/products/{p.id}")

    assert res.status_code == 200
    variants = res.json()["variants"]
    assert len(variants) == 1
    url = variants[0]["filled_template_url"]
    assert url.startswith("https://"), f"公開 endpoint 不可回 gs:// — 收到 {url!r}"


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


# ── Public Themes / Series ────────────────────────────────────────────────────


from product.models import Theme  # noqa: E402


async def _make_theme(db, *, name, sort_order=0, description=None, cover=None):
    t = Theme(
        name=name, description=description, cover_image_url=cover, sort_order=sort_order,
    )
    db.add(t)
    await db.flush()
    return t


async def _make_series(db, *, name, theme_id=None, description=None):
    s = ProductSeries(name=name, description=description, theme_id=theme_id)
    db.add(s)
    await db.flush()
    return s


@pytest.mark.asyncio
async def test_list_themes_includes_counts(client, db):
    """GET /themes 回傳所有主題，含 series_count 與 product_count（only on_sale）。"""
    theme = await _make_theme(db, name="萌寵", sort_order=10)
    series_a = await _make_series(db, name="貓咪", theme_id=theme.id)
    series_b = await _make_series(db, name="狗狗", theme_id=theme.id)

    job = await _make_job(db)
    p1 = await _make_product(db, title="貓 1", series_id=series_a.id)
    await _make_variant(db, p1.id, job.id)
    p2 = await _make_product(db, title="貓 2 草稿", status=ProductStatusEnum.draft, series_id=series_a.id)
    await _make_variant(db, p2.id, job.id)
    await db.commit()
    _ = series_b   # series_b 沒商品但仍計入 series_count

    res = await client.get("/api/v1/themes")
    assert res.status_code == 200
    body = res.json()
    matched = [t for t in body["items"] if t["name"] == "萌寵"]
    assert len(matched) == 1
    t = matched[0]
    assert t["series_count"] == 2
    assert t["product_count"] == 1   # 只算 on_sale，不算 draft


@pytest.mark.asyncio
async def test_get_theme_returns_nested_series(client, db):
    """GET /themes/{id} 回主題詳情 + 巢狀 series（含 product_count）。"""
    theme = await _make_theme(db, name="風景", description="美麗山景")
    series_a = await _make_series(db, name="高山", theme_id=theme.id)
    series_b = await _make_series(db, name="海岸", theme_id=theme.id)

    job = await _make_job(db)
    p1 = await _make_product(db, title="阿爾卑斯", series_id=series_a.id)
    await _make_variant(db, p1.id, job.id)
    await db.commit()
    _ = series_b

    res = await client.get(f"/api/v1/themes/{theme.id}")
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "風景"
    assert body["description"] == "美麗山景"
    series_names = {s["name"]: s["product_count"] for s in body["series"]}
    assert series_names == {"高山": 1, "海岸": 0}


@pytest.mark.asyncio
async def test_get_theme_not_found(client, db):
    import uuid as _uuid
    res = await client.get(f"/api/v1/themes/{_uuid.uuid4()}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_list_series_default_returns_all(client, db):
    theme = await _make_theme(db, name="主題A")
    s1 = await _make_series(db, name="系列 A1", theme_id=theme.id)
    s2 = await _make_series(db, name="系列 B1（無主題）", theme_id=None)
    await db.commit()
    _ = (s1, s2)

    res = await client.get("/api/v1/series")
    body = res.json()
    names = [s["name"] for s in body["items"]]
    assert "系列 A1" in names
    assert "系列 B1（無主題）" in names

    # 含 theme_name
    a1 = next(s for s in body["items"] if s["name"] == "系列 A1")
    assert a1["theme_name"] == "主題A"
    b1 = next(s for s in body["items"] if s["name"] == "系列 B1（無主題）")
    assert b1["theme_name"] is None


@pytest.mark.asyncio
async def test_list_series_filter_by_theme(client, db):
    theme_a = await _make_theme(db, name="A")
    theme_b = await _make_theme(db, name="B")
    s_a = await _make_series(db, name="A 的系列", theme_id=theme_a.id)
    s_b = await _make_series(db, name="B 的系列", theme_id=theme_b.id)
    await db.commit()
    _ = (s_a, s_b)

    res = await client.get(f"/api/v1/series?theme_id={theme_a.id}")
    body = res.json()
    names = [s["name"] for s in body["items"]]
    assert names == ["A 的系列"]


@pytest.mark.asyncio
async def test_get_series_returns_products_ordered_by_series_order(client, db):
    theme = await _make_theme(db, name="主題X")
    series = await _make_series(db, name="系列X", theme_id=theme.id)

    job = await _make_job(db)
    # series_order: 1, NULL, 2 → 預期排序：1, 2, NULL（NULL 最後）
    p1 = await _make_product(db, title="第一", series_id=series.id, series_order=1)
    p2 = await _make_product(db, title="未排", series_id=series.id, series_order=None)
    p3 = await _make_product(db, title="第二", series_id=series.id, series_order=2)
    await _make_variant(db, p1.id, job.id, price=500)
    await _make_variant(db, p2.id, job.id, price=600)
    await _make_variant(db, p3.id, job.id, price=700)
    await db.commit()

    res = await client.get(f"/api/v1/series/{series.id}")
    assert res.status_code == 200
    body = res.json()
    titles = [p["title"] for p in body["products"]]
    assert titles == ["第一", "第二", "未排"]
    assert body["theme_name"] == "主題X"


@pytest.mark.asyncio
async def test_get_series_excludes_draft(client, db):
    series = await _make_series(db, name="只 on_sale 的系列")
    job = await _make_job(db)
    p1 = await _make_product(db, title="上架", series_id=series.id)
    p2 = await _make_product(db, title="草稿", status=ProductStatusEnum.draft, series_id=series.id)
    await _make_variant(db, p1.id, job.id)
    await _make_variant(db, p2.id, job.id)
    await db.commit()

    res = await client.get(f"/api/v1/series/{series.id}")
    body = res.json()
    titles = [p["title"] for p in body["products"]]
    assert titles == ["上架"]


@pytest.mark.asyncio
async def test_get_series_not_found(client, db):
    import uuid as _uuid
    res = await client.get(f"/api/v1/series/{_uuid.uuid4()}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_products_filter_by_theme(client, db):
    """GET /products?theme_id=... 過濾該主題下所有系列的商品。"""
    theme_a = await _make_theme(db, name="主題A")
    theme_b = await _make_theme(db, name="主題B")
    series_a = await _make_series(db, name="系列A", theme_id=theme_a.id)
    series_b = await _make_series(db, name="系列B", theme_id=theme_b.id)

    job = await _make_job(db)
    p1 = await _make_product(db, title="A 的商品", series_id=series_a.id)
    p2 = await _make_product(db, title="B 的商品", series_id=series_b.id)
    await _make_variant(db, p1.id, job.id)
    await _make_variant(db, p2.id, job.id)
    await db.commit()

    res = await client.get(f"/api/v1/products?theme_id={theme_a.id}")
    body = res.json()
    titles = [p["title"] for p in body["items"]]
    assert titles == ["A 的商品"]


# Suppress unused-import warning
_ = (ProductImage, select)
