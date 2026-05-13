import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from auth.models import User

COLORS_URL = "/api/v1/admin/colors"

ADMIN_USER = {
    "name": "色庫管理員", "email": "color_admin@example.com", "password": "adminpass123"
}
CUSTOMER_USER = {
    "name": "一般用戶", "email": "color_customer@example.com", "password": "custpass123"
}

VALID_COLOR = {
    "code": "201",
    "name": "SKIN TONE",
    "color_family": "膚色系",
    "brand": None,
    "rgb": [247, 167, 132],
    "stock_ml": 500.0,
}


async def _make_admin(client, db):
    await client.post("/api/v1/auth/register", json=ADMIN_USER)
    result = await db.execute(select(User).where(User.email == ADMIN_USER["email"]))
    user = result.scalar_one()
    user.is_email_verified = True
    user.role = "admin"
    await db.commit()


async def _make_customer(client, db):
    await client.post("/api/v1/auth/register", json=CUSTOMER_USER)
    result = await db.execute(select(User).where(User.email == CUSTOMER_USER["email"]))
    user = result.scalar_one()
    user.is_email_verified = True
    await db.commit()


async def _login(client, email, password):
    res = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    if "access_token" in res.cookies:
        client.cookies.set("access_token", res.cookies["access_token"])


async def _create_color(client, db, data=None) -> dict:
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.post(COLORS_URL, json=data or VALID_COLOR)
    return res.json()


# ── GET /admin/colors ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_colors_empty(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.get(COLORS_URL)
    assert res.status_code == 200
    assert res.json()["items"] == []


@pytest.mark.asyncio
async def test_list_colors_with_data(client: AsyncClient, db):
    await _create_color(client, db)
    res = await client.get(COLORS_URL)
    assert res.status_code == 200
    assert len(res.json()["items"]) == 1


@pytest.mark.asyncio
async def test_list_colors_filter_family(client: AsyncClient, db):
    await _create_color(client, db)
    res = await client.get(COLORS_URL, params={"color_family": "膚色系"})
    assert res.status_code == 200
    assert len(res.json()["items"]) == 1

    res = await client.get(COLORS_URL, params={"color_family": "藍色系"})
    assert res.status_code == 200
    assert len(res.json()["items"]) == 0


@pytest.mark.asyncio
async def test_list_colors_filter_active(client: AsyncClient, db):
    color = await _create_color(client, db)
    await client.patch(f"{COLORS_URL}/{color['id']}/toggle-active")

    res = await client.get(COLORS_URL, params={"is_active": "false"})
    assert res.status_code == 200
    assert len(res.json()["items"]) == 1

    res = await client.get(COLORS_URL, params={"is_active": "true"})
    assert res.status_code == 200
    assert len(res.json()["items"]) == 0


@pytest.mark.asyncio
async def test_list_colors_search(client: AsyncClient, db):
    await _create_color(client, db)
    res = await client.get(COLORS_URL, params={"search": "SKIN"})
    assert res.status_code == 200
    assert len(res.json()["items"]) == 1

    res = await client.get(COLORS_URL, params={"search": "BLUE"})
    assert res.status_code == 200
    assert len(res.json()["items"]) == 0


@pytest.mark.asyncio
async def test_list_colors_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    assert (await client.get(COLORS_URL)).status_code == 403


@pytest.mark.asyncio
async def test_list_colors_unauthenticated(client: AsyncClient, db):
    assert (await client.get(COLORS_URL)).status_code == 401


# ── POST /admin/colors ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_color_ok(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.post(COLORS_URL, json=VALID_COLOR)
    assert res.status_code == 201
    data = res.json()
    assert data["code"] == "201"
    assert data["stock_ml"] == 500.0


@pytest.mark.asyncio
async def test_create_color_duplicate_code(client: AsyncClient, db):
    await _create_color(client, db)
    res = await client.post(COLORS_URL, json=VALID_COLOR)
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_create_color_invalid_rgb(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    bad = {**VALID_COLOR, "rgb": [300, 0, 0]}
    res = await client.post(COLORS_URL, json=bad)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_color_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    assert (await client.post(COLORS_URL, json=VALID_COLOR)).status_code == 403


@pytest.mark.asyncio
async def test_create_color_unauthenticated(client: AsyncClient, db):
    assert (await client.post(COLORS_URL, json=VALID_COLOR)).status_code == 401


# ── PUT /admin/colors/{id} ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_color_duplicate_code(client: AsyncClient, db):
    color = await _create_color(client, db)
    second = {**VALID_COLOR, "code": "202", "name": "SECOND COLOR"}
    await client.post(COLORS_URL, json=second)
    res = await client.put(
        f"{COLORS_URL}/{color['id']}",
        json={**VALID_COLOR, "code": "202"},
    )
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_update_color_ok(client: AsyncClient, db):
    color = await _create_color(client, db)
    updated = {**VALID_COLOR, "name": "UPDATED NAME"}
    res = await client.put(f"{COLORS_URL}/{color['id']}", json=updated)
    assert res.status_code == 200
    assert res.json()["name"] == "UPDATED NAME"


@pytest.mark.asyncio
async def test_update_color_not_found(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.put(f"{COLORS_URL}/{uuid.uuid4()}", json=VALID_COLOR)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_update_color_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    assert (await client.put(f"{COLORS_URL}/{uuid.uuid4()}", json=VALID_COLOR)).status_code == 403


@pytest.mark.asyncio
async def test_update_color_unauthenticated(client: AsyncClient, db):
    assert (await client.put(f"{COLORS_URL}/{uuid.uuid4()}", json=VALID_COLOR)).status_code == 401


# ── PUT /admin/colors/{id} 部分更新（PATCH 語義） ──────────────────────────────
# Regression：原本 UpdateColorRequest 把 code/name 列為必填，導致 admin 只想改
# color_family 時前端只送 {name, color_family} 就 422。修成全欄位 optional +
# model_fields_set 區分省略 vs 顯式 null。

@pytest.mark.asyncio
async def test_update_color_family_only(client: AsyncClient, db):
    """只送 color_family（user 實際遇到的 case）→ 其他欄位保留原值。"""
    color = await _create_color(client, db)
    res = await client.put(
        f"{COLORS_URL}/{color['id']}", json={"color_family": "green"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["color_family"] == "green"
    # 其他欄位保留
    assert body["code"] == VALID_COLOR["code"]
    assert body["name"] == VALID_COLOR["name"]
    assert body["stock_ml"] == VALID_COLOR["stock_ml"]


@pytest.mark.asyncio
async def test_update_color_stock_only(client: AsyncClient, db):
    """只送 stock_ml → 其他保留。"""
    color = await _create_color(client, db)
    res = await client.put(f"{COLORS_URL}/{color['id']}", json={"stock_ml": 999.5})
    assert res.status_code == 200
    assert res.json()["stock_ml"] == 999.5
    assert res.json()["color_family"] == VALID_COLOR["color_family"]


@pytest.mark.asyncio
async def test_update_color_clear_color_family_with_null(client: AsyncClient, db):
    """顯式送 color_family=null → 清空該欄位（DB 該欄位 nullable）。"""
    color = await _create_color(client, db)
    res = await client.put(
        f"{COLORS_URL}/{color['id']}", json={"color_family": None},
    )
    assert res.status_code == 200
    assert res.json()["color_family"] is None


@pytest.mark.asyncio
async def test_update_color_code_null_rejected(client: AsyncClient, db):
    """code 是 NOT NULL，顯式送 code=null → 422。"""
    color = await _create_color(client, db)
    res = await client.put(f"{COLORS_URL}/{color['id']}", json={"code": None})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_update_color_empty_body_rejected(client: AsyncClient, db):
    """空 body → 422（避免無意義呼叫）。"""
    color = await _create_color(client, db)
    res = await client.put(f"{COLORS_URL}/{color['id']}", json={})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_update_color_same_code_no_duplicate_check(client: AsyncClient, db):
    """code 沒變時不該觸發查重（修前的 service 不論 code 有無都查，浪費一次 query）。"""
    color = await _create_color(client, db)
    # 送跟原本一樣的 code，不應 409
    res = await client.put(
        f"{COLORS_URL}/{color['id']}", json={"code": color["code"], "name": "RENAMED"},
    )
    assert res.status_code == 200
    assert res.json()["name"] == "RENAMED"


# ── PATCH /admin/colors/{id}/toggle-active ────────────────────────────────────

@pytest.mark.asyncio
async def test_toggle_active_ok(client: AsyncClient, db):
    color = await _create_color(client, db)
    assert color["is_active"] is True

    res = await client.patch(f"{COLORS_URL}/{color['id']}/toggle-active")
    assert res.status_code == 200
    assert res.json()["is_active"] is False

    res = await client.patch(f"{COLORS_URL}/{color['id']}/toggle-active")
    assert res.json()["is_active"] is True


@pytest.mark.asyncio
async def test_toggle_active_not_found(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    assert (await client.patch(f"{COLORS_URL}/{uuid.uuid4()}/toggle-active")).status_code == 404


@pytest.mark.asyncio
async def test_toggle_active_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    assert (await client.patch(f"{COLORS_URL}/{uuid.uuid4()}/toggle-active")).status_code == 403


@pytest.mark.asyncio
async def test_toggle_active_unauthenticated(client: AsyncClient, db):
    assert (await client.patch(f"{COLORS_URL}/{uuid.uuid4()}/toggle-active")).status_code == 401


# ── PATCH /admin/colors/{id}/stock ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_add_stock_ok(client: AsyncClient, db):
    color = await _create_color(client, db)
    res = await client.patch(f"{COLORS_URL}/{color['id']}/stock", json={"add_ml": 250.0})
    assert res.status_code == 200
    data = res.json()
    assert data["new_stock_ml"] == 750.0
    assert data["fulfilled_orders"] == 0


@pytest.mark.asyncio
async def test_add_stock_invalid(client: AsyncClient, db):
    color = await _create_color(client, db)
    res = await client.patch(f"{COLORS_URL}/{color['id']}/stock", json={"add_ml": 0})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_add_stock_not_found(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    assert (
        await client.patch(f"{COLORS_URL}/{uuid.uuid4()}/stock", json={"add_ml": 100})
    ).status_code == 404


@pytest.mark.asyncio
async def test_add_stock_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    assert (
        await client.patch(f"{COLORS_URL}/{uuid.uuid4()}/stock", json={"add_ml": 100})
    ).status_code == 403


@pytest.mark.asyncio
async def test_add_stock_unauthenticated(client: AsyncClient, db):
    assert (
        await client.patch(f"{COLORS_URL}/{uuid.uuid4()}/stock", json={"add_ml": 100})
    ).status_code == 401


# ── GET /admin/colors/shortage-dashboard ──────────────────────────────────────

@pytest.mark.asyncio
async def test_shortage_dashboard_empty(client: AsyncClient, db):
    await _make_admin(client, db)
    await _login(client, ADMIN_USER["email"], ADMIN_USER["password"])
    res = await client.get(f"{COLORS_URL}/shortage-dashboard")
    assert res.status_code == 200
    assert res.json()["items"] == []


@pytest.mark.asyncio
async def test_shortage_dashboard_with_shortage(client: AsyncClient, db):
    """Spec 算法：待備量 = Σ(palette_color_mappings.required_ml × order_items.preorder_qty)。

    需要建立有 preorder_qty>0 的 active 訂單才會在 dashboard 顯示缺貨。
    """
    import uuid
    from uuid import UUID

    from auth.models import User
    from orders.models import Order, OrderItem, OrderStatusEnum
    from palette.models import PaletteColorMapping
    from production.models import ProductionJob

    color = await _create_color(client, db)
    job = ProductionJob(
        detail="standard", difficulty="beginner", mode="standard",
        canvas_w_cm=30, canvas_h_cm=40,
        palette_json=[{"template_id": 1, "rgb": {"r": 247, "g": 167, "b": 132}, "percent": 0.5}],
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    db.add(PaletteColorMapping(
        production_job_id=job.id,
        template_id=1,
        algorithm_rgb=[247, 167, 132],
        physical_color_id=UUID(color["id"]),
        required_ml=9999.0,
    ))

    # 建立含 preorder_qty 的 active 訂單觸發 shortage 計算
    user = (await db.execute(select(User).where(User.role == "admin"))).scalar_one()
    order = Order(
        order_number=f"PL-{uuid.uuid4().hex[:8]}",
        user_id=user.id,
        status=OrderStatusEnum.paid,
        subtotal=100, discount_amount=0, shipping_fee=0, total=100,
        shipping_type="home", shipping_snapshot={},
    )
    db.add(order)
    await db.flush()
    db.add(OrderItem(
        order_id=order.id,
        product_variant_id=None,
        production_job_id=job.id,
        product_title_snapshot="x",
        variant_spec_snapshot={},
        unit_price=100, quantity=1,
        fulfilled_qty=0, preorder_qty=1, is_returned=False,
    ))
    await db.commit()

    res = await client.get(f"{COLORS_URL}/shortage-dashboard")
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    assert items[0]["code"] == "201"
    assert items[0]["shortage_ml"] > 0
    assert items[0]["waiting_orders"] == 1


@pytest.mark.asyncio
async def test_shortage_dashboard_non_admin(client: AsyncClient, db):
    await _make_customer(client, db)
    await _login(client, CUSTOMER_USER["email"], CUSTOMER_USER["password"])
    assert (await client.get(f"{COLORS_URL}/shortage-dashboard")).status_code == 403


@pytest.mark.asyncio
async def test_shortage_dashboard_unauthenticated(client: AsyncClient, db):
    assert (await client.get(f"{COLORS_URL}/shortage-dashboard")).status_code == 401


# ── PATCH /admin/colors/{id}/rgb ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_rgb_with_hex(client: AsyncClient, db):
    color = await _create_color(client, db)
    res = await client.patch(
        f"{COLORS_URL}/{color['id']}/rgb", json={"hex": "#01020F"}
    )
    assert res.status_code == 200
    assert res.json()["rgb"] == [1, 2, 15]


@pytest.mark.asyncio
async def test_update_rgb_with_array(client: AsyncClient, db):
    color = await _create_color(client, db)
    res = await client.patch(
        f"{COLORS_URL}/{color['id']}/rgb", json={"rgb": [10, 20, 30]}
    )
    assert res.status_code == 200
    assert res.json()["rgb"] == [10, 20, 30]


@pytest.mark.asyncio
async def test_update_rgb_both_provided_rejected(client: AsyncClient, db):
    color = await _create_color(client, db)
    res = await client.patch(
        f"{COLORS_URL}/{color['id']}/rgb",
        json={"hex": "#FFFFFF", "rgb": [0, 0, 0]},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_update_rgb_neither_provided_rejected(client: AsyncClient, db):
    color = await _create_color(client, db)
    res = await client.patch(f"{COLORS_URL}/{color['id']}/rgb", json={})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_update_rgb_bad_hex_rejected(client: AsyncClient, db):
    color = await _create_color(client, db)
    res = await client.patch(
        f"{COLORS_URL}/{color['id']}/rgb", json={"hex": "ZZZZZZ"}
    )
    assert res.status_code == 422


# ── RGB History + Revert ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rgb_history_initial_after_create(client: AsyncClient, db):
    color = await _create_color(client, db)
    res = await client.get(f"{COLORS_URL}/{color['id']}/rgb-history")
    assert res.status_code == 200
    items = res.json()["items"]
    assert len(items) == 1
    assert items[0]["note"] == "initial"
    assert items[0]["rgb"] == VALID_COLOR["rgb"]


@pytest.mark.asyncio
async def test_rgb_history_after_update(client: AsyncClient, db):
    color = await _create_color(client, db)
    await client.patch(
        f"{COLORS_URL}/{color['id']}/rgb", json={"rgb": [10, 20, 30]}
    )
    res = await client.get(f"{COLORS_URL}/{color['id']}/rgb-history")
    items = res.json()["items"]
    assert len(items) == 2
    # 倒序：最新在前
    assert items[0]["note"] == "manual"
    assert items[0]["rgb"] == [10, 20, 30]
    assert items[1]["note"] == "initial"


@pytest.mark.asyncio
async def test_revert_rgb_success(client: AsyncClient, db):
    color = await _create_color(client, db)
    # 改一次 RGB
    await client.patch(
        f"{COLORS_URL}/{color['id']}/rgb", json={"rgb": [10, 20, 30]}
    )
    # 取 history，找到 initial 那筆
    history = (
        await client.get(f"{COLORS_URL}/{color['id']}/rgb-history")
    ).json()["items"]
    initial = next(h for h in history if h["note"] == "initial")
    # 還原
    res = await client.post(
        f"{COLORS_URL}/{color['id']}/rgb-revert",
        json={"history_id": initial["id"]},
    )
    assert res.status_code == 200
    assert res.json()["rgb"] == VALID_COLOR["rgb"]
    # 還原後又多一筆 history
    new_history = (
        await client.get(f"{COLORS_URL}/{color['id']}/rgb-history")
    ).json()["items"]
    assert len(new_history) == 3
    assert new_history[0]["note"].startswith("revert from")


@pytest.mark.asyncio
async def test_revert_rgb_invalid_history_404(client: AsyncClient, db):
    color = await _create_color(client, db)
    fake_id = str(uuid.uuid4())
    res = await client.post(
        f"{COLORS_URL}/{color['id']}/rgb-revert",
        json={"history_id": fake_id},
    )
    assert res.status_code == 404


# ── PATCH /admin/colors/{id}/stock — 升單流程 ────────────────────────────────


async def _seed_preorder_order(db, color_id, *, preorder_qty=1, required_ml=10.0):
    """建立一張 paid 的 order，order_item.preorder_qty=N，連結到 production_job 與 mapping。"""
    from palette.models import PaletteColorMapping
    from production.models import ProductionJob

    job = ProductionJob(
        detail="standard", difficulty="beginner", mode="standard",
        canvas_w_cm=30, canvas_h_cm=40,
    )
    db.add(job)
    await db.flush()
    db.add(PaletteColorMapping(
        production_job_id=job.id,
        template_id=1,
        algorithm_rgb=[247, 167, 132],
        physical_color_id=color_id,
        required_ml=required_ml,
    ))
    user = (await db.execute(select(User).where(User.role == "admin"))).scalar_one()
    from orders.models import (
        Order,
        OrderItem,
        OrderStatusEnum,
        ProductionProgress,
    )
    order = Order(
        order_number=f"PL-{uuid.uuid4().hex[:8]}",
        user_id=user.id,
        status=OrderStatusEnum.paid,
        subtotal=100, discount_amount=0, shipping_fee=0, total=100,
        shipping_type="home", shipping_snapshot={},
    )
    db.add(order)
    await db.flush()
    item = OrderItem(
        order_id=order.id,
        product_variant_id=None,
        production_job_id=job.id,
        product_title_snapshot="x",
        variant_spec_snapshot={},
        unit_price=100, quantity=preorder_qty,
        fulfilled_qty=0, preorder_qty=preorder_qty, is_returned=False,
    )
    db.add(item)
    await db.flush()
    db.add(ProductionProgress(order_item_id=item.id))
    await db.commit()
    return order, item


@pytest.mark.asyncio
async def test_add_stock_upgrades_preorder_when_sufficient(client: AsyncClient, db):
    """進貨足夠 → fulfilled_qty 升單、preorder_qty=0、stock 扣減、order paid→processing。"""
    from uuid import UUID

    from notifications.models import AdminNotification
    from orders.models import (
        Order,
        OrderItem,
        OrderStatusEnum,
        ProductionProgress,
        ProductionProgressStatusEnum,
    )
    color_data = {**VALID_COLOR, "stock_ml": 0}
    color = await _create_color(client, db, data=color_data)
    order, item = await _seed_preorder_order(
        db, UUID(color["id"]), preorder_qty=2, required_ml=5.0,
    )
    # 進貨 100ml，需要 5 × 2 = 10ml，足夠
    res = await client.patch(
        f"{COLORS_URL}/{color['id']}/stock", json={"add_ml": 100}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["fulfilled_orders"] == 1
    assert body["new_stock_ml"] == 90.0  # 100 - 10

    refreshed_item = (await db.execute(
        select(OrderItem).where(OrderItem.id == item.id)
        .execution_options(populate_existing=True)
    )).scalar_one()
    assert refreshed_item.fulfilled_qty == 2
    assert refreshed_item.preorder_qty == 0

    refreshed_order = (await db.execute(
        select(Order).where(Order.id == order.id)
        .execution_options(populate_existing=True)
    )).scalar_one()
    assert refreshed_order.status == OrderStatusEnum.processing

    progress = (await db.execute(
        select(ProductionProgress).where(ProductionProgress.order_item_id == item.id)
        .execution_options(populate_existing=True)
    )).scalar_one()
    assert progress.status == ProductionProgressStatusEnum.in_production

    # 應有一筆 preorder_upgraded 通知
    notif = (await db.execute(
        select(AdminNotification).where(
            AdminNotification.type == "preorder_upgraded",
            AdminNotification.reference_id == order.id,
        )
    )).scalar_one_or_none()
    assert notif is not None


@pytest.mark.asyncio
async def test_add_stock_skips_when_insufficient(client: AsyncClient, db):
    """進貨不足 → 不升單，order 維持 paid、產生 stock_shortage 通知。"""
    from uuid import UUID

    from notifications.models import AdminNotification
    from orders.models import Order, OrderItem, OrderStatusEnum

    color_data = {**VALID_COLOR, "stock_ml": 0}
    color = await _create_color(client, db, data=color_data)
    order, item = await _seed_preorder_order(
        db, UUID(color["id"]), preorder_qty=2, required_ml=50.0,
    )
    # 進貨 50ml，需要 50 × 2 = 100ml，不足
    res = await client.patch(
        f"{COLORS_URL}/{color['id']}/stock", json={"add_ml": 50}
    )
    body = res.json()
    assert body["fulfilled_orders"] == 0
    assert body["new_stock_ml"] == 50.0  # 沒扣

    refreshed_item = (await db.execute(
        select(OrderItem).where(OrderItem.id == item.id)
        .execution_options(populate_existing=True)
    )).scalar_one()
    assert refreshed_item.fulfilled_qty == 0
    assert refreshed_item.preorder_qty == 2

    refreshed_order = (await db.execute(
        select(Order).where(Order.id == order.id)
        .execution_options(populate_existing=True)
    )).scalar_one()
    assert refreshed_order.status == OrderStatusEnum.paid

    # 應有一筆 stock_shortage 通知
    shortage = (await db.execute(
        select(AdminNotification).where(
            AdminNotification.type == "stock_shortage",
            AdminNotification.reference_id == UUID(color["id"]),
        )
    )).scalar_one_or_none()
    assert shortage is not None


@pytest.mark.asyncio
async def test_add_stock_no_preorder_no_side_effects(client: AsyncClient, db):
    """沒 preorder 訂單，進貨單純加 stock，無升單、無通知。"""
    color = await _create_color(client, db)
    res = await client.patch(
        f"{COLORS_URL}/{color['id']}/stock", json={"add_ml": 50}
    )
    assert res.status_code == 200
    assert res.json()["fulfilled_orders"] == 0
    assert res.json()["new_stock_ml"] == 550.0


@pytest.mark.asyncio
async def test_add_stock_rejects_too_large(client: AsyncClient, db):
    color = await _create_color(client, db)
    res = await client.patch(
        f"{COLORS_URL}/{color['id']}/stock", json={"add_ml": 9_999_999}
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_add_stock_rejects_three_decimals(client: AsyncClient, db):
    color = await _create_color(client, db)
    res = await client.patch(
        f"{COLORS_URL}/{color['id']}/stock", json={"add_ml": 12.345}
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_add_stock_together_preference_does_not_progress(
    client: AsyncClient, db
):
    """規格 §43：shipping_preference='together' 即使整張 order 預購全備齊也不自動推進。"""
    from uuid import UUID

    from orders.models import Order, OrderStatusEnum, ShippingPreferenceEnum
    color_data = {**VALID_COLOR, "stock_ml": 0}
    color = await _create_color(client, db, data=color_data)
    order, item = await _seed_preorder_order(
        db, UUID(color["id"]), preorder_qty=1, required_ml=5.0,
    )
    order.shipping_preference = ShippingPreferenceEnum.together
    await db.commit()

    res = await client.patch(
        f"{COLORS_URL}/{color['id']}/stock", json={"add_ml": 100}
    )
    assert res.status_code == 200

    refreshed_order = (await db.execute(
        select(Order).where(Order.id == order.id)
        .execution_options(populate_existing=True)
    )).scalar_one()
    assert refreshed_order.status == OrderStatusEnum.paid
    _ = item


@pytest.mark.asyncio
async def test_put_color_only_changes_metadata(client: AsyncClient, db):
    """PUT 不允許改 RGB（必須走 PATCH /rgb 保留 audit）。"""
    color = await _create_color(client, db)
    res = await client.put(
        f"{COLORS_URL}/{color['id']}",
        json={
            "code": "999", "name": "改名後",
            "color_family": "new_family", "brand": "新品牌",
            "stock_ml": 100,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["code"] == "999"
    assert body["name"] == "改名後"
    # RGB 不在 PUT schema 中，原值保留
    assert body["rgb"] == VALID_COLOR["rgb"]


@pytest.mark.asyncio
async def test_put_color_with_rgb_field_ignored(client: AsyncClient, db):
    """PUT body 帶 rgb 欄位也不會生效（pydantic 預設 ignore extra）。"""
    color = await _create_color(client, db)
    res = await client.put(
        f"{COLORS_URL}/{color['id']}",
        json={
            "code": color["code"], "name": color["name"],
            "color_family": color["color_family"], "brand": color["brand"],
            "stock_ml": 0,
            "rgb": [0, 0, 0],
        },
    )
    assert res.status_code in (200, 422)
    if res.status_code == 200:
        # 確認 RGB 仍是原值
        list_res = await client.get(COLORS_URL)
        c = next(c for c in list_res.json()["items"] if c["id"] == color["id"])
        assert c["rgb"] == VALID_COLOR["rgb"]
