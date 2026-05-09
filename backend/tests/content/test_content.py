"""Module 13 — Content management tests."""

import bcrypt
import pytest
from sqlalchemy import select

from auth.models import User
from color.models import SystemSetting
from content.models import CaseCategory, CustomCase, Page
from custom.models import CustomPhotoPrice, CustomPhotoSurcharge

ADMIN_EMAIL = "content_admin@test.com"
ADMIN_PASS = "adminpass123"


async def _make_admin(db):
    admin = User(
        name="ContentAdmin",
        email=ADMIN_EMAIL,
        password_hash=bcrypt.hashpw(ADMIN_PASS.encode(), bcrypt.gensalt()).decode(),
        role="admin",
        is_active=True,
        is_email_verified=True,
    )
    db.add(admin)
    await db.commit()
    return admin


async def _login_admin(client):
    res = await client.post("/api/v1/admin/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASS,
    })
    if "access_token" in res.cookies:
        client.cookies.set("access_token", res.cookies["access_token"])
    return res


async def _seed_page(db, slug="size_guide", title="尺寸指南", content="說明..."):
    p = Page(slug=slug, title=title, content=content)
    db.add(p)
    await db.commit()
    return p


# ── Pages ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_page_existing(client, db):
    await _seed_page(db, slug="shipping", title="運送", content="...")
    res = await client.get("/api/v1/pages/shipping")
    assert res.status_code == 200
    assert res.json()["title"] == "運送"


@pytest.mark.asyncio
async def test_get_page_not_found(client, db):
    res = await client.get("/api/v1/pages/nonexistent_slug")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_admin_list_pages(client, db):
    await _make_admin(db)
    await _seed_page(db, slug="a", title="A", content="...")
    await _seed_page(db, slug="b", title="B", content="...")
    await _login_admin(client)
    res = await client.get("/api/v1/admin/pages")
    assert res.status_code == 200
    assert len(res.json()["items"]) >= 2


@pytest.mark.asyncio
async def test_admin_upsert_new_page(client, db):
    await _make_admin(db)
    await _login_admin(client)
    res = await client.put(
        "/api/v1/admin/pages/new_slug",
        json={"title": "新頁", "content": "新內容"},
    )
    assert res.status_code == 200
    assert res.json()["title"] == "新頁"

    db_check = await db.execute(select(Page).where(Page.slug == "new_slug"))
    assert db_check.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_admin_update_existing_page(client, db):
    await _make_admin(db)
    await _seed_page(db, slug="size_guide", title="舊", content="舊內容")
    await _login_admin(client)
    res = await client.put(
        "/api/v1/admin/pages/size_guide",
        json={"title": "新標題", "content": "更新內容"},
    )
    assert res.status_code == 200
    assert res.json()["title"] == "新標題"


# ── System Settings ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_public_settings_whitelist(client, db):
    db.add(SystemSetting(key="bank_account_number", value="123-456"))
    db.add(SystemSetting(key="ECPAY_HASH_KEY", value="secret"))
    db.add(SystemSetting(key="quote_reply_days", value="3"))
    await db.commit()
    res = await client.get("/api/v1/system-settings/public")
    body = res.json()["items"]
    assert "bank_account_number" in body
    assert "quote_reply_days" in body
    assert "ECPAY_HASH_KEY" not in body  # not whitelisted


@pytest.mark.asyncio
async def test_admin_list_settings(client, db):
    await _make_admin(db)
    db.add(SystemSetting(key="x", value="1"))
    db.add(SystemSetting(key="y", value="2"))
    await db.commit()
    await _login_admin(client)
    res = await client.get("/api/v1/admin/system-settings")
    assert res.status_code == 200
    keys = [s["key"] for s in res.json()["items"]]
    assert "x" in keys and "y" in keys


@pytest.mark.asyncio
async def test_admin_upsert_new_setting(client, db):
    await _make_admin(db)
    await _login_admin(client)
    res = await client.patch(
        "/api/v1/admin/system-settings",
        json={"key": "free_shipping_amount", "value": "800"},
    )
    assert res.status_code == 200
    assert res.json()["value"] == "800"


@pytest.mark.asyncio
async def test_admin_update_existing_setting(client, db):
    await _make_admin(db)
    db.add(SystemSetting(key="foo", value="old"))
    await db.commit()
    await _login_admin(client)
    res = await client.patch(
        "/api/v1/admin/system-settings",
        json={"key": "foo", "value": "new"},
    )
    assert res.status_code == 200
    assert res.json()["value"] == "new"


# ── Custom Cases ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_public_cases_published_only(client, db):
    db.add(CustomCase(image_url="a.png", title="Pub", is_published=True))
    db.add(CustomCase(image_url="b.png", title="Hide", is_published=False))
    await db.commit()
    res = await client.get("/api/v1/custom-cases")
    titles = [c["title"] for c in res.json()["items"]]
    assert "Pub" in titles
    assert "Hide" not in titles


@pytest.mark.asyncio
async def test_public_cases_filter_category(client, db):
    cat = CaseCategory(name="人像")
    db.add(cat)
    await db.flush()
    db.add(CustomCase(image_url="a.png", title="人像案", category_id=cat.id, is_published=True))
    db.add(CustomCase(image_url="b.png", title="風景案", is_published=True))
    await db.commit()
    res = await client.get(f"/api/v1/custom-cases?category_id={cat.id}")
    titles = [c["title"] for c in res.json()["items"]]
    assert titles == ["人像案"]


@pytest.mark.asyncio
async def test_public_case_unpublished_404(client, db):
    case = CustomCase(image_url="a.png", title="Hide", is_published=False)
    db.add(case)
    await db.commit()
    res = await client.get(f"/api/v1/custom-cases/{case.id}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_admin_create_case(client, db):
    await _make_admin(db)
    await _login_admin(client)
    res = await client.post(
        "/api/v1/admin/custom-cases",
        json={
            "image_url": "https://example.com/a.png",
            "title": "新案",
            "description": "說明",
            "canvas_w_cm": 30, "canvas_h_cm": 40,
            "difficulty": "beginner",
            "is_published": True,
        },
    )
    assert res.status_code == 201
    assert res.json()["title"] == "新案"


@pytest.mark.asyncio
async def test_admin_update_case(client, db):
    await _make_admin(db)
    case = CustomCase(image_url="a.png", title="舊", is_published=True)
    db.add(case)
    await db.commit()
    await _login_admin(client)
    res = await client.put(
        f"/api/v1/admin/custom-cases/{case.id}",
        json={"title": "新", "description": "改過"},
    )
    assert res.status_code == 200
    assert res.json()["title"] == "新"


@pytest.mark.asyncio
async def test_admin_delete_case(client, db):
    await _make_admin(db)
    case = CustomCase(image_url="a.png", title="刪", is_published=True)
    db.add(case)
    await db.commit()
    await _login_admin(client)
    res = await client.delete(f"/api/v1/admin/custom-cases/{case.id}")
    assert res.status_code == 204
    db_check = await db.execute(select(CustomCase).where(CustomCase.id == case.id))
    assert db_check.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_admin_toggle_publish_case(client, db):
    await _make_admin(db)
    case = CustomCase(image_url="a.png", title="切換", is_published=False)
    db.add(case)
    await db.commit()
    await _login_admin(client)
    res = await client.patch(f"/api/v1/admin/custom-cases/{case.id}/toggle-publish")
    assert res.status_code == 200
    assert res.json()["is_published"] is True


# ── case_images（多圖 + 排序）────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_create_case_with_multiple_images(client, db):
    await _make_admin(db)
    await _login_admin(client)
    res = await client.post(
        "/api/v1/admin/custom-cases",
        json={
            "title": "多圖案例",
            "is_published": True,
            "images": [
                {"image_url": "https://example.com/1.png"},
                {"image_url": "https://example.com/2.png"},
                {"image_url": "https://example.com/3.png"},
            ],
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    # image_url 應自動同步為第一張
    assert body["image_url"] == "https://example.com/1.png"
    # images 陣列照順序回，sort_order 0/1/2
    assert len(body["images"]) == 3
    assert [i["sort_order"] for i in body["images"]] == [0, 1, 2]
    assert body["images"][0]["image_url"] == "https://example.com/1.png"
    assert body["images"][2]["image_url"] == "https://example.com/3.png"


@pytest.mark.asyncio
async def test_admin_create_case_legacy_single_image_url(client, db):
    """向後相容：只傳 image_url（沒給 images）→ 自動建一筆 sort_order=0 的 case_image。"""
    await _make_admin(db)
    await _login_admin(client)
    res = await client.post(
        "/api/v1/admin/custom-cases",
        json={
            "image_url": "https://example.com/legacy.png",
            "title": "舊版單圖",
        },
    )
    assert res.status_code == 201
    body = res.json()
    assert len(body["images"]) == 1
    assert body["images"][0]["image_url"] == "https://example.com/legacy.png"
    assert body["images"][0]["sort_order"] == 0


@pytest.mark.asyncio
async def test_admin_create_case_no_image_rejected(client, db):
    """既無 image_url 也無 images → 409 拒絕。"""
    await _make_admin(db)
    await _login_admin(client)
    res = await client.post(
        "/api/v1/admin/custom-cases",
        json={"title": "沒圖"},
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_admin_update_case_replace_images_reorders(client, db):
    """傳 images 列表 → 整批替換並重新編 sort_order；首張 URL 同步到 image_url。"""
    await _make_admin(db)
    await _login_admin(client)
    create_res = await client.post(
        "/api/v1/admin/custom-cases",
        json={
            "title": "init",
            "images": [
                {"image_url": "https://e.com/A.png"},
                {"image_url": "https://e.com/B.png"},
            ],
        },
    )
    cid = create_res.json()["id"]

    # 重新排序：B 放第一、新增 C
    update_res = await client.put(
        f"/api/v1/admin/custom-cases/{cid}",
        json={
            "images": [
                {"image_url": "https://e.com/B.png"},
                {"image_url": "https://e.com/C.png"},
                {"image_url": "https://e.com/A.png"},
            ],
        },
    )
    assert update_res.status_code == 200
    body = update_res.json()
    urls = [i["image_url"] for i in body["images"]]
    assert urls == [
        "https://e.com/B.png",
        "https://e.com/C.png",
        "https://e.com/A.png",
    ]
    # image_url 同步成新首張 = B
    assert body["image_url"] == "https://e.com/B.png"


@pytest.mark.asyncio
async def test_admin_update_case_empty_images_rejected(client, db):
    await _make_admin(db)
    await _login_admin(client)
    create_res = await client.post(
        "/api/v1/admin/custom-cases",
        json={
            "title": "init",
            "images": [{"image_url": "https://e.com/X.png"}],
        },
    )
    cid = create_res.json()["id"]
    res = await client.put(
        f"/api/v1/admin/custom-cases/{cid}",
        json={"images": []},
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_admin_update_case_omit_images_keeps_existing(client, db):
    """不傳 images → 只改其他欄位，case_images 不動。"""
    await _make_admin(db)
    await _login_admin(client)
    create_res = await client.post(
        "/api/v1/admin/custom-cases",
        json={
            "title": "init",
            "images": [
                {"image_url": "https://e.com/x.png"},
                {"image_url": "https://e.com/y.png"},
            ],
        },
    )
    cid = create_res.json()["id"]

    update_res = await client.put(
        f"/api/v1/admin/custom-cases/{cid}",
        json={"title": "renamed"},
    )
    assert update_res.status_code == 200
    body = update_res.json()
    assert body["title"] == "renamed"
    assert len(body["images"]) == 2
    assert body["images"][0]["image_url"] == "https://e.com/x.png"


@pytest.mark.asyncio
async def test_public_get_case_returns_images(client, db):
    await _make_admin(db)
    await _login_admin(client)
    create_res = await client.post(
        "/api/v1/admin/custom-cases",
        json={
            "title": "公開",
            "is_published": True,
            "images": [
                {"image_url": "https://e.com/1.png"},
                {"image_url": "https://e.com/2.png"},
            ],
        },
    )
    cid = create_res.json()["id"]
    client.cookies.clear()  # 用未登入打公開
    res = await client.get(f"/api/v1/custom-cases/{cid}")
    assert res.status_code == 200
    body = res.json()
    assert len(body["images"]) == 2
    assert body["images"][0]["sort_order"] == 0


# ── Case Categories ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_case_categories_crud(client, db):
    await _make_admin(db)
    await _login_admin(client)

    # Create
    res = await client.post(
        "/api/v1/admin/case-categories", json={"name": "新分類"}
    )
    assert res.status_code == 201
    cat_id = res.json()["id"]

    # List
    res = await client.get("/api/v1/admin/case-categories")
    names = [c["name"] for c in res.json()["items"]]
    assert "新分類" in names

    # Update
    res = await client.put(
        f"/api/v1/admin/case-categories/{cat_id}", json={"name": "更名"}
    )
    assert res.status_code == 200
    assert res.json()["name"] == "更名"

    # Delete
    res = await client.delete(f"/api/v1/admin/case-categories/{cat_id}")
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_delete_category_sets_null(client, db):
    """ON DELETE SET NULL: removing a category nulls custom_cases.category_id."""
    await _make_admin(db)
    cat = CaseCategory(name="待刪")
    db.add(cat)
    await db.flush()
    case = CustomCase(image_url="a.png", title="關聯", category_id=cat.id, is_published=True)
    db.add(case)
    await db.commit()

    await _login_admin(client)
    await client.delete(f"/api/v1/admin/case-categories/{cat.id}")

    db_check = await db.execute(
        select(CustomCase).where(CustomCase.id == case.id)
        .execution_options(populate_existing=True)
    )
    refreshed = db_check.scalar_one()
    assert refreshed.category_id is None


# ── Custom Photo Prices ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_list_photo_prices(client, db):
    await _make_admin(db)
    db.add(CustomPhotoPrice(canvas_w=30, canvas_h=40, difficulty="beginner", price=500))
    db.add(CustomPhotoPrice(canvas_w=50, canvas_h=50, difficulty="intermediate", price=900))
    await db.commit()
    await _login_admin(client)
    res = await client.get("/api/v1/admin/custom-photo-prices")
    assert res.status_code == 200
    assert len(res.json()["items"]) == 2


@pytest.mark.asyncio
async def test_admin_update_photo_price(client, db):
    await _make_admin(db)
    p = CustomPhotoPrice(canvas_w=30, canvas_h=40, difficulty="beginner", price=500)
    db.add(p)
    await db.commit()
    await _login_admin(client)
    res = await client.put(
        f"/api/v1/admin/custom-photo-prices/{p.id}", json={"price": 600}
    )
    assert res.status_code == 200
    assert res.json()["price"] == 600.0


# ── Custom Photo Surcharges ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_surcharges_crud(client, db):
    await _make_admin(db)
    await _login_admin(client)

    # Create
    res = await client.post(
        "/api/v1/admin/custom-photo-surcharges",
        json={"category": "人物數量", "label": "2人", "amount": 200},
    )
    assert res.status_code == 201
    sid = res.json()["id"]

    # List
    res = await client.get("/api/v1/admin/custom-photo-surcharges")
    assert any(s["id"] == sid for s in res.json()["items"])

    # Update
    res = await client.put(
        f"/api/v1/admin/custom-photo-surcharges/{sid}",
        json={"amount": 250},
    )
    assert res.status_code == 200
    assert res.json()["amount"] == 250.0

    # Delete
    res = await client.delete(f"/api/v1/admin/custom-photo-surcharges/{sid}")
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_admin_toggle_active_surcharge(client, db):
    await _make_admin(db)
    s = CustomPhotoSurcharge(category="cat", label="lbl", amount=100, is_active=True)
    db.add(s)
    await db.commit()
    await _login_admin(client)
    res = await client.patch(
        f"/api/v1/admin/custom-photo-surcharges/{s.id}/toggle-active"
    )
    assert res.status_code == 200
    assert res.json()["is_active"] is False


# ── Auth guards ───────────────────────────────────────────────────────────────


CUSTOMER_EMAIL = "content_user@test.com"
CUSTOMER_PASS = "userpass123"


async def _make_customer(db):
    user = User(
        name="ContentUser",
        email=CUSTOMER_EMAIL,
        password_hash=bcrypt.hashpw(CUSTOMER_PASS.encode(), bcrypt.gensalt()).decode(),
        role="customer",
        is_active=True,
        is_email_verified=True,
    )
    db.add(user)
    await db.commit()
    return user


async def _login_customer(client):
    res = await client.post("/api/v1/auth/login", json={
        "email": CUSTOMER_EMAIL, "password": CUSTOMER_PASS,
    })
    if "access_token" in res.cookies:
        client.cookies.set("access_token", res.cookies["access_token"])


@pytest.mark.asyncio
async def test_admin_endpoints_unauthenticated_blocked(client, db):
    """Hit one endpoint per admin group without auth — expect 401."""
    res = await client.get("/api/v1/admin/pages")
    assert res.status_code == 401
    res = await client.get("/api/v1/admin/system-settings")
    assert res.status_code == 401
    res = await client.get("/api/v1/admin/custom-cases")
    assert res.status_code == 401
    res = await client.get("/api/v1/admin/case-categories")
    assert res.status_code == 401
    res = await client.get("/api/v1/admin/custom-photo-prices")
    assert res.status_code == 401
    res = await client.get("/api/v1/admin/custom-photo-surcharges")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_admin_endpoints_customer_role_blocked(client, db):
    await _make_customer(db)
    await _login_customer(client)
    for path in [
        "/api/v1/admin/pages",
        "/api/v1/admin/system-settings",
        "/api/v1/admin/custom-cases",
        "/api/v1/admin/case-categories",
        "/api/v1/admin/custom-photo-prices",
        "/api/v1/admin/custom-photo-surcharges",
    ]:
        res = await client.get(path)
        assert res.status_code == 403, f"{path} should be 403, got {res.status_code}"


@pytest.mark.asyncio
async def test_admin_update_case_clears_nullable_field(client, db):
    """Sending {description: null} should null out description in DB."""
    await _make_admin(db)
    case = CustomCase(image_url="a.png", title="t", description="原本有", is_published=True)
    db.add(case)
    await db.commit()
    await _login_admin(client)
    res = await client.put(
        f"/api/v1/admin/custom-cases/{case.id}", json={"description": None}
    )
    assert res.status_code == 200
    assert res.json()["description"] is None


@pytest.mark.asyncio
async def test_admin_update_case_invalid_category_id(client, db):
    """Updating a case to a non-existent category_id should 404, not 500."""
    import uuid
    await _make_admin(db)
    case = CustomCase(image_url="a.png", title="t", is_published=True)
    db.add(case)
    await db.commit()
    await _login_admin(client)
    res = await client.put(
        f"/api/v1/admin/custom-cases/{case.id}",
        json={"category_id": str(uuid.uuid4())},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_page_invalid_slug_pattern(client, db):
    """Path-traversal-like or non-conforming slugs should 422."""
    res = await client.get("/api/v1/pages/Bad-Slug")
    assert res.status_code == 422
    res = await client.get("/api/v1/pages/UPPER")
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_system_setting_key_format_rejected(client, db):
    await _make_admin(db)
    await _login_admin(client)
    # Uppercase rejected
    res = await client.patch(
        "/api/v1/admin/system-settings",
        json={"key": "BadKey", "value": "x"},
    )
    assert res.status_code == 422
    # Starting with digit rejected
    res = await client.patch(
        "/api/v1/admin/system-settings",
        json={"key": "1foo", "value": "x"},
    )
    assert res.status_code == 422
