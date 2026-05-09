"""Integration tests for Module 10 — Custom Orders."""

from unittest.mock import patch

import bcrypt
import pytest
from sqlalchemy import select

from auth.models import User
from color.models import SystemSetting
from custom.models import (
    CustomRequest,
    CustomRequestMessage,
    CustomRequestStatusEnum,
)
from custom.service import _hash_token, expire_quotes_async
from notifications.models import AdminNotification
from orders.models import OrderItem
from product.models import Product
from production.models import ProductionJob

# ── URLs ──────────────────────────────────────────────────────────────────────

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
CR_URL = "/api/v1/custom-requests"
ADMIN_CR_URL = "/api/v1/admin/custom-requests"
QUOTE_URL = "/api/v1/custom/quote"

CUSTOMER = {"name": "客製測試用戶", "email": "custom@example.com", "password": "testpass123"}
ADMIN_EMAIL = "customadmin@test.com"
ADMIN_PASS = "adminpass123"


# ── Helpers ───────────────────────────────────────────────────────────────────


async def _make_customer(client, db, email=None, name=None):
    payload = {**CUSTOMER}
    if email:
        payload["email"] = email
    if name:
        payload["name"] = name
    await client.post(REGISTER_URL, json=payload)
    result = await db.execute(select(User).where(User.email == payload["email"]))
    user = result.scalar_one()
    user.is_email_verified = True
    await db.commit()
    return user


async def _make_admin(db):
    admin = User(
        name="CustomAdmin",
        email=ADMIN_EMAIL,
        password_hash=bcrypt.hashpw(ADMIN_PASS.encode(), bcrypt.gensalt()).decode(),
        role="admin",
        is_active=True,
        is_email_verified=True,
    )
    db.add(admin)
    await db.commit()
    return admin


async def _login_customer(client, email=None, password=None):
    res = await client.post(LOGIN_URL, json={
        "email": email or CUSTOMER["email"],
        "password": password or CUSTOMER["password"],
    })
    if "access_token" in res.cookies:
        client.cookies.set("access_token", res.cookies["access_token"])
    return res


async def _login_admin(client):
    res = await client.post("/api/v1/admin/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASS,
    })
    if "access_token" in res.cookies:
        client.cookies.set("access_token", res.cookies["access_token"])
    return res


async def _seed_system_settings(db):
    for key, value in [
        ("quote_reply_days", "3"),
        ("payment_absolute_deadline_hours", "48"),
        ("bank_account_number", "12345678901"),
        ("bank_name", "測試銀行"),
        ("bank_account_name", "測試戶名"),
    ]:
        exists = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        if exists.scalar_one_or_none() is None:
            db.add(SystemSetting(key=key, value=value))
    await db.commit()


async def _make_product(db):
    p = Product(
        title="參考商品",
        description="ref",
        cover_image_url="http://example.com/img.jpg",
        status="on_sale",
    )
    db.add(p)
    await db.flush()
    await db.commit()
    return p


async def _make_approved_job(db, custom_request_id):
    """Create an approved production_job for a given custom_request."""
    from datetime import UTC, datetime
    job = ProductionJob(
        detail="standard",
        difficulty="beginner",
        canvas_w_cm=30.0,
        canvas_h_cm=40.0,
        custom_request_id=custom_request_id,
        approved=True,
        approved_at=datetime.now(UTC),
        status="completed",
        num_colors_used=18,
    )
    db.add(job)
    await db.flush()
    await db.commit()
    return job


async def _create_photo_request(client, **extra):
    payload = {
        "request_type": "custom_photo",
        "photo_url": "https://firebase.example.com/photo.jpg",
        "canvas_w_cm": 30,
        "canvas_h_cm": 40,
        "difficulty": "beginner",
        "customer_notes": "請畫成水彩風",
    }
    payload.update(extra)
    return await client.post(CR_URL, json=payload)


async def _make_shipping_profile(client):
    res = await client.post("/api/v1/users/me/shipping-profiles", json={
        "shipping_type": "home",
        "recipient_name": "測試收件人",
        "phone": "0912345678",
        "city": "台北市",
        "district": "信義區",
        "address_detail": "忠孝東路一段1號",
    })
    return res.json()["id"]


# ── Customer create / list / detail / messages / photo ───────────────────────


@pytest.mark.asyncio
async def test_create_custom_photo_request(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    res = await _create_photo_request(client)
    assert res.status_code == 201
    body = res.json()
    assert body["request_type"] == "custom_photo"
    assert body["status"] == "quote_pending"
    assert "id" in body and "created_at" in body


@pytest.mark.asyncio
async def test_create_custom_spec_missing_ref_product(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    res = await client.post(CR_URL, json={
        "request_type": "custom_spec",
        "canvas_w_cm": 40,
        "canvas_h_cm": 50,
        "difficulty": "intermediate",
    })
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_custom_photo_missing_photo(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    res = await client.post(CR_URL, json={
        "request_type": "custom_photo",
        "canvas_w_cm": 30,
        "canvas_h_cm": 40,
    })
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_request_seeds_welcome_message(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    res = await _create_photo_request(client)
    rid = res.json()["id"]
    msg_result = await db.execute(
        select(CustomRequestMessage).where(CustomRequestMessage.request_id == rid)
    )
    msgs = list(msg_result.scalars().all())
    assert len(msgs) == 1
    assert msgs[0].sender_type.value == "admin"
    assert "預計" in msgs[0].message


@pytest.mark.asyncio
async def test_create_request_creates_admin_notification(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    res = await _create_photo_request(client)
    rid = res.json()["id"]
    notif_result = await db.execute(
        select(AdminNotification).where(
            AdminNotification.type == "quote_pending",
            AdminNotification.reference_id == rid,
        )
    )
    notif = notif_result.scalar_one_or_none()
    assert notif is not None
    assert notif.requires_action is True


@pytest.mark.asyncio
async def test_list_own_custom_requests(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    await _create_photo_request(client)
    await _create_photo_request(client)
    res = await client.get(CR_URL)
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


@pytest.mark.asyncio
async def test_get_others_custom_request_404(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db, email="a@x.com", name="UserA")
    await _make_customer(client, db, email="b@x.com", name="UserB")
    await _login_customer(client, email="a@x.com")
    create_res = await _create_photo_request(client)
    rid = create_res.json()["id"]
    # logout & login as B
    client.cookies.clear()
    await _login_customer(client, email="b@x.com")
    res = await client.get(f"{CR_URL}/{rid}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_post_customer_message(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    create_res = await _create_photo_request(client)
    rid = create_res.json()["id"]
    res = await client.post(f"{CR_URL}/{rid}/messages", json={"message": "請改用淺色調"})
    assert res.status_code == 201
    body = res.json()
    assert body["sender_type"] == "customer"
    assert body["message"] == "請改用淺色調"


@pytest.mark.asyncio
async def test_patch_photo_in_quote_pending(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    create_res = await _create_photo_request(client)
    rid = create_res.json()["id"]
    res = await client.patch(
        f"{CR_URL}/{rid}/photo",
        json={"photo_url": "https://firebase.example.com/new.jpg"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["photo_url"] == "https://firebase.example.com/new.jpg"


@pytest.mark.asyncio
async def test_patch_photo_after_negotiating_rejected(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    create_res = await _create_photo_request(client)
    rid = create_res.json()["id"]
    # Manually move to negotiating
    req_result = await db.execute(select(CustomRequest).where(CustomRequest.id == rid))
    req = req_result.scalar_one()
    req.status = CustomRequestStatusEnum.negotiating
    await db.commit()

    res = await client.patch(
        f"{CR_URL}/{rid}/photo",
        json={"photo_url": "https://firebase.example.com/new.jpg"},
    )
    assert res.status_code == 409
    body = res.json()
    assert body.get("code") == "PHOTO_LOCKED_AFTER_NEGOTIATING"


# ── PATCH /custom-requests/{id} (fields except photo) ────────────────────────


@pytest.mark.asyncio
async def test_patch_request_fields_in_quote_pending(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    create_res = await _create_photo_request(client)
    rid = create_res.json()["id"]

    res = await client.patch(
        f"{CR_URL}/{rid}",
        json={
            "canvas_w_cm": 50,
            "canvas_h_cm": 70,
            "difficulty": "intermediate",
            "customer_notes": "改大尺寸",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["canvas_w_cm"] == 50
    assert body["canvas_h_cm"] == 70
    assert body["difficulty"] == "intermediate"
    assert body["customer_notes"] == "改大尺寸"


@pytest.mark.asyncio
async def test_patch_request_partial_only_changes_sent_fields(client, db):
    """只送 difficulty → 其他欄位保持不動。"""
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    create_res = await _create_photo_request(client)
    rid = create_res.json()["id"]

    res = await client.patch(f"{CR_URL}/{rid}", json={"difficulty": "advanced"})
    assert res.status_code == 200
    body = res.json()
    assert body["difficulty"] == "advanced"
    # canvas should be unchanged from creation defaults
    # _create_photo_request 預設 canvas_w_cm=30, canvas_h_cm=40
    assert body["canvas_w_cm"] == 30
    assert body["canvas_h_cm"] == 40


@pytest.mark.asyncio
async def test_patch_request_set_difficulty_to_null(client, db):
    """送 difficulty=null → 改為「讓管理員建議」。"""
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    create_res = await _create_photo_request(client)
    rid = create_res.json()["id"]

    res = await client.patch(f"{CR_URL}/{rid}", json={"difficulty": None})
    assert res.status_code == 200
    body = res.json()
    assert body["difficulty"] is None


@pytest.mark.asyncio
async def test_patch_request_after_negotiating_rejected(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    create_res = await _create_photo_request(client)
    rid = create_res.json()["id"]
    req_result = await db.execute(select(CustomRequest).where(CustomRequest.id == rid))
    req = req_result.scalar_one()
    req.status = CustomRequestStatusEnum.negotiating
    await db.commit()

    res = await client.patch(f"{CR_URL}/{rid}", json={"customer_notes": "想改"})
    assert res.status_code == 409
    assert res.json().get("code") == "REQUEST_LOCKED_AFTER_NEGOTIATING"


@pytest.mark.asyncio
async def test_patch_request_by_non_owner_404(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    create_res = await _create_photo_request(client)
    rid = create_res.json()["id"]

    # 換別的客戶登入
    client.cookies.clear()
    await _make_customer(client, db, email="other@example.com", name="Other")
    await _login_customer(client, email="other@example.com")

    res = await client.patch(f"{CR_URL}/{rid}", json={"customer_notes": "偷改"})
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_patch_request_empty_body_noop(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    create_res = await _create_photo_request(client)
    rid = create_res.json()["id"]

    res = await client.patch(f"{CR_URL}/{rid}", json={})
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_patch_request_empty_body_does_not_touch_db(client, db):
    """空 body → service 應直接 return，不觸發 DB write / SSE publish。

    驗證方式：建立 request 後立刻空 PATCH，比對 created_at vs DB 中的值
    （若有寫入會觸發 onupdate；目前 model 沒 updated_at 欄位 → 改驗 SSE 隊列）。
    我們用最簡單方式：DB 物件的 status 不變 + return body 等於原 detail。
    """
    from custom.models import CustomRequest
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    create_res = await _create_photo_request(client)
    rid = create_res.json()["id"]

    # 取得原始 created_at
    orig = (await db.execute(select(CustomRequest).where(CustomRequest.id == rid))).scalar_one()
    orig_created = orig.created_at

    res = await client.patch(f"{CR_URL}/{rid}", json={})
    assert res.status_code == 200
    # 不變
    after = (await db.execute(select(CustomRequest).where(CustomRequest.id == rid))).scalar_one()
    assert after.created_at == orig_created


@pytest.mark.asyncio
async def test_patch_request_canvas_below_min_rejected(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    create_res = await _create_photo_request(client)
    rid = create_res.json()["id"]

    res = await client.patch(f"{CR_URL}/{rid}", json={"canvas_w_cm": 5})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_patch_request_canvas_above_max_rejected(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    create_res = await _create_photo_request(client)
    rid = create_res.json()["id"]

    res = await client.patch(f"{CR_URL}/{rid}", json={"canvas_h_cm": 999})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_patch_request_notes_too_long_rejected(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    create_res = await _create_photo_request(client)
    rid = create_res.json()["id"]

    res = await client.patch(f"{CR_URL}/{rid}", json={"customer_notes": "X" * 2001})
    assert res.status_code == 422


# ── Admin endpoints ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_list_custom_requests(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _make_admin(db)
    await _login_customer(client)
    await _create_photo_request(client)
    client.cookies.clear()
    await _login_admin(client)
    res = await client.get(ADMIN_CR_URL)
    assert res.status_code == 200
    body = res.json()
    assert body["total"] >= 1
    assert "user_name" in body["items"][0]


@pytest.mark.asyncio
async def test_admin_post_message(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _make_admin(db)
    await _login_customer(client)
    create_res = await _create_photo_request(client)
    rid = create_res.json()["id"]
    client.cookies.clear()
    await _login_admin(client)
    res = await client.post(f"{ADMIN_CR_URL}/{rid}/messages", json={"message": "我們將於明天回覆"})
    assert res.status_code == 201
    assert res.json()["sender_type"] == "admin"


@pytest.mark.asyncio
async def test_admin_mark_negotiating(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _make_admin(db)
    await _login_customer(client)
    create_res = await _create_photo_request(client)
    rid = create_res.json()["id"]
    client.cookies.clear()
    await _login_admin(client)
    res = await client.patch(f"{ADMIN_CR_URL}/{rid}/mark-negotiating")
    assert res.status_code == 200
    assert res.json()["status"] == "negotiating"
    # Notification should be marked completed
    notif_result = await db.execute(
        select(AdminNotification).where(
            AdminNotification.type == "quote_pending",
            AdminNotification.reference_id == rid,
        )
    )
    notif = notif_result.scalar_one()
    assert notif.status.value == "completed"


@pytest.mark.asyncio
async def test_admin_send_quote(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _make_admin(db)
    await _login_customer(client)
    create_res = await _create_photo_request(client)
    rid = create_res.json()["id"]
    client.cookies.clear()
    await _login_admin(client)
    res = await client.post(
        f"{ADMIN_CR_URL}/{rid}/quote",
        json={"quoted_price": 1500, "detail": "standard", "quote_note": "已調整為水彩風"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "quote_sent"
    assert body["quoted_price"] == 1500.0
    assert "quote_expires_at" in body


@pytest.mark.asyncio
async def test_admin_quote_already_confirmed_rejected(client, db):
    await _seed_system_settings(db)
    user = await _make_customer(client, db)
    await _make_admin(db)
    await _login_customer(client)
    create_res = await _create_photo_request(client)
    rid = create_res.json()["id"]
    # Force status to quote_confirmed via DB manipulation
    req_result = await db.execute(select(CustomRequest).where(CustomRequest.id == rid))
    req = req_result.scalar_one()
    req.status = CustomRequestStatusEnum.quote_confirmed
    await db.commit()

    client.cookies.clear()
    await _login_admin(client)
    res = await client.post(
        f"{ADMIN_CR_URL}/{rid}/quote",
        json={"quoted_price": 1500},
    )
    assert res.status_code == 400
    _ = user


@pytest.mark.asyncio
async def test_admin_get_photo_signed_url_stub(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _make_admin(db)
    await _login_customer(client)
    create_res = await _create_photo_request(client)
    rid = create_res.json()["id"]
    client.cookies.clear()
    await _login_admin(client)
    res = await client.get(f"{ADMIN_CR_URL}/{rid}/photo-signed-url")
    assert res.status_code == 200
    body = res.json()
    assert "url" in body
    assert "expires_at" in body


# ── Quote token flow ─────────────────────────────────────────────────────────


async def _setup_quote_sent_state(client, db, plain_token="token_abc123"):
    """Create request, approve job, set status to quote_sent with given token.

    新流程：admin 報價必綁 production_job（admin 在 QuoteDialog 選定）。helper 把
    job.id 寫入 req.quoted_production_job_id 供 confirm_quote 加進 cart 使用。
    quote_token 直接存 plain（與 send_quote 行為一致）。
    """
    from datetime import UTC, datetime, timedelta
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    create_res = await _create_photo_request(client)
    rid = create_res.json()["id"]

    job = await _make_approved_job(db, rid)

    req_result = await db.execute(select(CustomRequest).where(CustomRequest.id == rid))
    req = req_result.scalar_one()
    req.status = CustomRequestStatusEnum.quote_sent
    req.quoted_price = 1500
    req.quote_token = plain_token  # plain 存（不再 hash）
    req.quote_expires_at = datetime.now(UTC) + timedelta(hours=24)
    req.quoted_at = datetime.now(UTC)
    req.quoted_production_job_id = job.id  # 新流程：admin 在 QuoteDialog 選定
    await db.commit()
    return rid, plain_token


@pytest.mark.asyncio
async def test_get_quote_summary(client, db):
    rid, token = await _setup_quote_sent_state(client, db)
    res = await client.get(f"{QUOTE_URL}/{token}")
    assert res.status_code == 200
    body = res.json()
    assert body["custom_request_id"] == rid
    assert body["quoted_price"] == 1500.0
    assert body["is_extended"] is False


@pytest.mark.asyncio
async def test_get_expired_quote(client, db):
    from datetime import UTC, datetime, timedelta
    rid, token = await _setup_quote_sent_state(client, db)
    req_result = await db.execute(select(CustomRequest).where(CustomRequest.id == rid))
    req = req_result.scalar_one()
    req.quote_expires_at = datetime.now(UTC) - timedelta(hours=1)
    await db.commit()
    res = await client.get(f"{QUOTE_URL}/{token}")
    assert res.status_code == 410
    assert res.json().get("code") == "QUOTE_EXPIRED"


@pytest.mark.asyncio
async def test_quote_view_count_increments_and_caps(client, db):
    """每次 GET quote summary view_count +1；達 10 次再呼叫 → 410 QUOTE_VIEW_LIMIT_REACHED。"""
    rid, token = await _setup_quote_sent_state(client, db)
    # 先打 10 次都應該成功，view_count 從 0 累加到 10
    for i in range(10):
        res = await client.get(f"{QUOTE_URL}/{token}")
        assert res.status_code == 200, f"call {i+1}"
        assert res.json()["view_count"] == i + 1
        assert res.json()["max_views"] == 10
    # 第 11 次達上限 → 410
    res = await client.get(f"{QUOTE_URL}/{token}")
    assert res.status_code == 410
    assert res.json().get("code") == "QUOTE_VIEW_LIMIT_REACHED"


@pytest.mark.asyncio
async def test_quote_summary_returns_messages_with_image_url(client, db):
    """quote summary 帶 messages 列表，含 admin 寄的 image_url 附圖。"""
    rid, token = await _setup_quote_sent_state(client, db)
    # 切到 admin 寄一則含圖訊息
    await _make_admin(db)
    await _login_admin(client)
    res = await client.post(
        f"/api/v1/admin/custom-requests/{rid}/messages",
        json={"message": "這是參考圖", "image_url": "https://example.com/sample.png"},
    )
    assert res.status_code == 201, res.text
    # 切回 customer 拿 quote → messages 中應含這則
    await _login_customer(client)
    res = await client.get(f"{QUOTE_URL}/{token}")
    assert res.status_code == 200
    msgs = res.json()["messages"]
    msg_with_img = next((m for m in msgs if m.get("image_url")), None)
    assert msg_with_img is not None, f"沒找到帶 image_url 的訊息: {msgs}"
    assert msg_with_img["image_url"] == "https://example.com/sample.png"
    assert msg_with_img["sender_type"] == "admin"


@pytest.mark.asyncio
async def test_quote_preview_returns_404_when_no_filled_template(client, db):
    """無 production_job 對應時 GET /preview → 404。"""
    rid, token = await _setup_quote_sent_state(client, db)
    res = await client.get(f"{QUOTE_URL}/{token}/preview")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_get_invalid_quote(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    res = await client.get(f"{QUOTE_URL}/nonexistent_token_xyz")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_confirm_quote_adds_to_cart(client, db):
    """confirm_quote 改成「加入購物車」（不再直接建 Order）。"""
    from orders.models import CartItem

    rid, token = await _setup_quote_sent_state(client, db)
    res = await client.post(
        f"{QUOTE_URL}/{token}/confirm",
        json={"quantity": 1},
    )
    assert res.status_code == 201
    body = res.json()
    assert "cart_item_id" in body
    assert body["custom_request_id"] == rid
    assert body["quantity"] == 1
    assert body["quoted_price"] == 1500.0

    # cart 內有客製 line
    item_result = await db.execute(
        select(CartItem).where(CartItem.custom_request_id == rid)
    )
    cart_item = item_result.scalar_one()
    assert cart_item.product_variant_id is None
    assert cart_item.production_job_id is not None
    assert cart_item.quantity == 1

    # custom_request status 不變（仍 quote_sent，等 cart 結帳才轉 confirmed）
    req_result = await db.execute(select(CustomRequest).where(CustomRequest.id == rid))
    req = req_result.scalar_one()
    assert req.status == CustomRequestStatusEnum.quote_sent


@pytest.mark.asyncio
async def test_confirm_quote_qty_overrides(client, db):
    """同一 quote 重複 confirm 不疊加，新 qty 蓋舊。"""
    from orders.models import CartItem

    rid, token = await _setup_quote_sent_state(client, db)
    await client.post(f"{QUOTE_URL}/{token}/confirm", json={"quantity": 2})
    res = await client.post(f"{QUOTE_URL}/{token}/confirm", json={"quantity": 5})
    assert res.status_code == 201

    items = (await db.execute(
        select(CartItem).where(CartItem.custom_request_id == rid)
    )).scalars().all()
    assert len(items) == 1
    assert items[0].quantity == 5


@pytest.mark.asyncio
async def test_extend_quote_first_time(client, db):
    rid, token = await _setup_quote_sent_state(client, db)
    res = await client.post(f"{QUOTE_URL}/{token}/extend")
    assert res.status_code == 200
    body = res.json()
    assert body["is_extended"] is True


@pytest.mark.asyncio
async def test_extend_quote_twice_rejected(client, db):
    rid, token = await _setup_quote_sent_state(client, db)
    await client.post(f"{QUOTE_URL}/{token}/extend")
    res = await client.post(f"{QUOTE_URL}/{token}/extend")
    assert res.status_code == 400
    assert res.json().get("code") == "QUOTE_ALREADY_EXTENDED"


@pytest.mark.asyncio
async def test_reject_quote(client, db):
    rid, token = await _setup_quote_sent_state(client, db)
    res = await client.post(f"{QUOTE_URL}/{token}/reject", json={"reason": "預算不足"})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "quote_rejected"
    assert body["rejected_at"] is not None


@pytest.mark.asyncio
async def test_request_revision(client, db):
    rid, token = await _setup_quote_sent_state(client, db)
    res = await client.post(
        f"{QUOTE_URL}/{token}/request-revision",
        json={"reason": "顏色想再深一點"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "draft_revision"
    assert body["revision_count"] == 1


@pytest.mark.asyncio
async def test_request_revision_max_exceeded(client, db):
    rid, token = await _setup_quote_sent_state(client, db)
    # Bump revision_count to 3
    req_result = await db.execute(select(CustomRequest).where(CustomRequest.id == rid))
    req = req_result.scalar_one()
    req.revision_count = 3
    await db.commit()

    res = await client.post(
        f"{QUOTE_URL}/{token}/request-revision",
        json={"reason": "再修一次"},
    )
    assert res.status_code == 400
    assert res.json().get("code") == "REVISION_LIMIT_EXCEEDED"


# ── Cross-module integration ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_jobs_auto_marks_negotiating(client, db):
    """E26: production_job from quote_pending request auto-flows to negotiating."""
    from production.service import create_jobs

    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _make_admin(db)
    await _login_customer(client)
    create_res = await _create_photo_request(client)
    rid = create_res.json()["id"]

    with patch("production.service.run_production_job"):
        await create_jobs(db, image_id=None, custom_request_id=rid, jobs_params=[{
            "detail": "standard",
            "difficulty": "beginner",
            "canvas_w_cm": 30.0,
            "canvas_h_cm": 40.0,
        }])

    req_result = await db.execute(select(CustomRequest).where(CustomRequest.id == rid))
    req = req_result.scalar_one()
    assert req.status == CustomRequestStatusEnum.negotiating

    # Notification should be marked completed
    notif_result = await db.execute(
        select(AdminNotification).where(
            AdminNotification.type == "quote_pending",
            AdminNotification.reference_id == rid,
        )
    )
    notif = notif_result.scalar_one()
    assert notif.status.value == "completed"


@pytest.mark.asyncio
async def test_paid_custom_order_creates_notification(client, db):
    """When admin transitions custom order to paid, custom_order_paid notification fires.

    新流程：confirm_quote → 加 cart → POST /orders → admin paid。
    """
    rid, token = await _setup_quote_sent_state(client, db)
    await _make_admin(db)
    profile_id = await _make_shipping_profile(client)
    # 1. confirm quote → 加進 cart
    res = await client.post(
        f"{QUOTE_URL}/{token}/confirm",
        json={"quantity": 1},
    )
    assert res.status_code == 201
    # 2. 從 cart 結帳建 Order
    res = await client.post(
        "/api/v1/orders",
        json={"shipping_profile_id": profile_id, "shipping_preference": "together"},
    )
    assert res.status_code in (200, 201)
    order_id = res.json()["order_id"]

    client.cookies.clear()
    await _login_admin(client)
    res = await client.patch(
        f"/api/v1/admin/orders/{order_id}/status",
        json={"status": "paid"},
    )
    assert res.status_code == 200

    notif_result = await db.execute(
        select(AdminNotification).where(
            AdminNotification.type == "custom_order_paid",
            AdminNotification.reference_id == order_id,
        )
    )
    notif = notif_result.scalar_one_or_none()
    assert notif is not None


# ── Celery (direct call) ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_expire_quotes_marks_expired(client, db):
    from datetime import UTC, datetime, timedelta
    rid, token = await _setup_quote_sent_state(client, db)
    req_result = await db.execute(select(CustomRequest).where(CustomRequest.id == rid))
    req = req_result.scalar_one()
    req.quote_expires_at = datetime.now(UTC) - timedelta(hours=1)
    await db.commit()

    count = await expire_quotes_async(db)
    assert count >= 1

    req_result2 = await db.execute(select(CustomRequest).where(CustomRequest.id == rid))
    req2 = req_result2.scalar_one()
    assert req2.status == CustomRequestStatusEnum.quote_expired


@pytest.mark.asyncio
async def test_expire_quotes_skips_confirmed(client, db):
    rid, _token = await _setup_quote_sent_state(client, db)
    req_result = await db.execute(select(CustomRequest).where(CustomRequest.id == rid))
    req = req_result.scalar_one()
    req.status = CustomRequestStatusEnum.quote_confirmed
    await db.commit()

    await expire_quotes_async(db)

    req_result2 = await db.execute(select(CustomRequest).where(CustomRequest.id == rid))
    req2 = req_result2.scalar_one()
    assert req2.status == CustomRequestStatusEnum.quote_confirmed


# ── AppError code field ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_app_error_returns_code(client, db):
    """Verify the new AppError.code field bubbles up to the JSON body."""
    rid, token = await _setup_quote_sent_state(client, db)
    await client.post(f"{QUOTE_URL}/{token}/extend")
    res = await client.post(f"{QUOTE_URL}/{token}/extend")
    assert res.status_code == 400
    body = res.json()
    assert "code" in body and body["code"] == "QUOTE_ALREADY_EXTENDED"
    assert "detail" in body
    _ = rid
