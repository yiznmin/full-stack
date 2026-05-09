"""Integration tests for Module 09 — Orders."""

import bcrypt
import pytest
from sqlalchemy import select

from auth.models import User
from color.models import PhysicalColor, SystemSetting
from discount.models import CouponConfig, CouponTypeEnum, DiscountTypeEnum, UserCoupon
from notifications.models import AdminNotification
from orders.models import (
    Order,
    OrderItem,
    OrderStatusEnum,
    PaymentSubmission,
    ProductionProgress,
)
from palette.models import PaletteColorMapping
from product.models import Product, ProductVariant
from production.models import ProductionJob

# ── URLs ───────────────────────────────────────────────────────────────────────

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
CART_URL = "/api/v1/cart"
CART_ITEMS_URL = "/api/v1/cart/items"
ORDERS_URL = "/api/v1/orders"
ADMIN_ORDERS_URL = "/api/v1/admin/orders"

CUSTOMER = {"name": "訂單測試用戶", "email": "orders@example.com", "password": "testpass123"}
ADMIN_EMAIL = "ordersadmin@test.com"
ADMIN_PASS = "adminpass123"

# ── Helpers ────────────────────────────────────────────────────────────────────


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
        name="OrdersAdmin",
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
        ("bank_account_number", "12345678901"),
        ("bank_name", "測試銀行"),
        ("bank_account_name", "測試戶名"),
        ("payment_absolute_deadline_hours", "48"),
    ]:
        existing = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
        if existing.scalar_one_or_none() is None:
            db.add(SystemSetting(key=key, value=value))
    await db.commit()


async def _make_production_job(db):
    job = ProductionJob(
        detail="standard",
        difficulty="beginner",
        canvas_w_cm=20.0,
        canvas_h_cm=20.0,
    )
    db.add(job)
    await db.flush()
    return job


async def _make_product_and_variant(db, job_id, price=500.0, is_active=True):
    product = Product(
        title="測試畫布",
        description="Test",
        cover_image_url="http://example.com/img.jpg",
        status="on_sale",
    )
    db.add(product)
    await db.flush()

    variant = ProductVariant(
        product_id=product.id,
        production_job_id=job_id,
        price=price,
        price_formula_base=price,
        is_active=is_active,
    )
    db.add(variant)
    await db.flush()
    return product, variant


async def _add_to_cart(client, variant_id, quantity=1):
    return await client.post(CART_ITEMS_URL, json={
        "variant_id": str(variant_id),
        "quantity": quantity,
    })


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


async def _create_order(client, **extra):
    """Create order using a freshly created home shipping profile."""
    profile_id = await _make_shipping_profile(client)
    payload = {"shipping_profile_id": profile_id}
    payload.update(extra)
    return await client.post(ORDERS_URL, json=payload)


# ── Cart Tests ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_empty_cart(client, db):
    await _make_customer(client, db)
    await _login_customer(client)
    res = await client.get(CART_URL)
    assert res.status_code == 200
    data = res.json()
    assert data["items"] == []
    assert data["subtotal"] == 0


@pytest.mark.asyncio
async def test_add_cart_item(client, db):
    await _make_customer(client, db)
    await _login_customer(client)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id)
    await db.commit()

    res = await _add_to_cart(client, variant.id, quantity=2)
    assert res.status_code == 201
    assert res.json()["quantity"] == 2


@pytest.mark.asyncio
async def test_add_inactive_variant_rejected(client, db):
    await _make_customer(client, db)
    await _login_customer(client)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, is_active=False)
    await db.commit()

    res = await _add_to_cart(client, variant.id)
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_add_same_variant_accumulates(client, db):
    await _make_customer(client, db)
    await _login_customer(client)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id)
    await db.commit()

    await _add_to_cart(client, variant.id, quantity=1)
    await _add_to_cart(client, variant.id, quantity=2)

    res = await client.get(CART_URL)
    assert res.status_code == 200
    assert res.json()["items"][0]["quantity"] == 3


@pytest.mark.asyncio
async def test_update_cart_item_quantity(client, db):
    await _make_customer(client, db)
    await _login_customer(client)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id)
    await db.commit()

    add_res = await _add_to_cart(client, variant.id, quantity=3)
    item_id = add_res.json()["id"]

    res = await client.patch(f"{CART_ITEMS_URL}/{item_id}", json={"quantity": 5})
    assert res.status_code == 200
    assert res.json()["quantity"] == 5


@pytest.mark.asyncio
async def test_update_cart_item_zero_deletes(client, db):
    await _make_customer(client, db)
    await _login_customer(client)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id)
    await db.commit()

    add_res = await _add_to_cart(client, variant.id, quantity=1)
    item_id = add_res.json()["id"]

    res = await client.patch(f"{CART_ITEMS_URL}/{item_id}", json={"quantity": 0})
    assert res.status_code == 200
    assert res.json()["deleted"] is True

    cart_res = await client.get(CART_URL)
    assert cart_res.json()["items"] == []


@pytest.mark.asyncio
async def test_delete_cart_item(client, db):
    await _make_customer(client, db)
    await _login_customer(client)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id)
    await db.commit()

    add_res = await _add_to_cart(client, variant.id, quantity=1)
    item_id = add_res.json()["id"]

    res = await client.delete(f"{CART_ITEMS_URL}/{item_id}")
    assert res.status_code == 204

    cart_res = await client.get(CART_URL)
    assert cart_res.json()["items"] == []


@pytest.mark.asyncio
async def test_delete_other_users_cart_item_returns_404(client, db):
    await _make_customer(client, db, email="user1orders@example.com", name="用戶一二三四")
    await _make_customer(client, db, email="user2orders@example.com", name="用戶五六七八")
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id)
    await db.commit()

    # user1 adds item
    await _login_customer(client, email="user1orders@example.com")
    add_res = await _add_to_cart(client, variant.id)
    item_id = add_res.json()["id"]

    # user2 tries to delete
    await _login_customer(client, email="user2orders@example.com")
    res = await client.delete(f"{CART_ITEMS_URL}/{item_id}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_checkout_preview_with_discount_and_free_shipping(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=500.0)
    await db.commit()

    await _add_to_cart(client, variant.id, quantity=2)

    res = await client.post("/api/v1/cart/checkout-preview", json={"shipping_type": "home"})
    assert res.status_code == 200
    data = res.json()
    assert data["subtotal"] == 1000.0
    assert data["shipping_fee"] == 0.0  # >= 800 free shipping
    assert data["total"] == 1000.0


# ── Order Creation Tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_order_success(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=500.0)
    await db.commit()

    await _add_to_cart(client, variant.id, quantity=1)

    res = await _create_order(client)
    assert res.status_code == 201
    data = res.json()
    assert "order_id" in data
    assert "order_number" in data
    assert data["order_number"].startswith("PL-")
    assert data["total"] == 620.0  # 500 + 120 shipping


@pytest.mark.asyncio
async def test_create_order_free_shipping(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=900.0)
    await db.commit()

    await _add_to_cart(client, variant.id, quantity=1)

    res = await _create_order(client)
    assert res.status_code == 201
    assert res.json()["total"] == 900.0


@pytest.mark.asyncio
async def test_create_order_inactive_variant_rejected(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id)
    await db.commit()

    # Add to cart while active
    await _add_to_cart(client, variant.id, quantity=1)

    # Deactivate variant
    variant.is_active = False
    await db.commit()

    res = await _create_order(client)
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_create_order_with_user_coupon(client, db):
    await _seed_system_settings(db)
    user = await _make_customer(client, db)
    await _login_customer(client)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=500.0)

    coupon = UserCoupon(
        user_id=user.id,
        coupon_config_id=None,
        promo_code_id=None,
        discount_type=DiscountTypeEnum.fixed,
        discount_value=100,
        is_used=False,
    )
    # Need a config to satisfy CHECK constraint
    config = CouponConfig(
        coupon_type=CouponTypeEnum.manual,
        discount_type=DiscountTypeEnum.fixed,
        discount_value=100,
        is_active=True,
        params={},
    )
    db.add(config)
    await db.flush()
    coupon.coupon_config_id = config.id
    db.add(coupon)
    await db.commit()

    await _add_to_cart(client, variant.id, quantity=1)

    res = await _create_order(client, user_coupon_id=str(coupon.id))
    assert res.status_code == 201
    data = res.json()
    # 500 - 100 + 120 = 520
    assert data["total"] == 520.0


@pytest.mark.asyncio
async def test_create_order_with_preorder_split(client, db):
    """When stock covers only part of the quantity, fulfilled_qty + preorder_qty = total."""
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=300.0)

    # Create a physical color with only 10ml stock
    color = PhysicalColor(
        code="TEST001", name="測試色", rgb=[100, 100, 100], stock_ml=10.0
    )
    db.add(color)
    await db.flush()

    # Map this color to the job with required_ml=5 (can fulfill max 2 units from 10ml)
    mapping = PaletteColorMapping(
        production_job_id=job.id,
        template_id=1,
        algorithm_rgb=[100, 100, 100],
        physical_color_id=color.id,
        required_ml=5.0,
    )
    db.add(mapping)
    await db.commit()

    # Add 3 units to cart (only 2 can be fulfilled)
    await _add_to_cart(client, variant.id, quantity=3)

    res = await _create_order(client)
    assert res.status_code == 201

    order_id = res.json()["order_id"]
    item_result = await db.execute(
        select(OrderItem).where(OrderItem.order_id == order_id)
    )
    item = item_result.scalar_one()
    assert item.fulfilled_qty == 2
    assert item.preorder_qty == 1
    assert item.fulfilled_qty + item.preorder_qty == item.quantity


# ── Customer Order Query Tests ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_orders(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=300.0)
    await db.commit()

    await _add_to_cart(client, variant.id)
    await _create_order(client)

    res = await client.get(ORDERS_URL)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_get_order_detail(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=300.0)
    await db.commit()

    await _add_to_cart(client, variant.id)
    create_res = await _create_order(client)
    order_id = create_res.json()["order_id"]

    res = await client.get(f"{ORDERS_URL}/{order_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == order_id
    assert data["can_cancel"] is True
    assert data["can_confirm_received"] is False


@pytest.mark.asyncio
async def test_get_other_users_order_returns_404(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db, email="u1orders@example.com", name="用戶一二三四")
    await _make_customer(client, db, email="u2orders@example.com", name="用戶五六七八")

    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=300.0)
    await db.commit()

    await _login_customer(client, email="u1orders@example.com")
    await _add_to_cart(client, variant.id)
    create_res = await _create_order(client)
    order_id = create_res.json()["order_id"]

    await _login_customer(client, email="u2orders@example.com")
    res = await client.get(f"{ORDERS_URL}/{order_id}")
    assert res.status_code == 404


# ── Payment Submission Tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_submit_payment(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=300.0)
    await db.commit()

    await _add_to_cart(client, variant.id)
    create_res = await _create_order(client)
    order_id = create_res.json()["order_id"]

    res = await client.post(f"{ORDERS_URL}/{order_id}/payment-submission", json={
        "transfer_amount": 420.0,
        "transfer_date": "2026-04-23",
        "transfer_time": "14:30:00",
        "account_last5": "12345",
    })
    assert res.status_code == 201
    body = res.json()
    assert body["transfer_amount"] == 420.0
    assert body["account_last5"] == "12345"
    assert body["is_flagged"] is False
    assert "id" in body and "created_at" in body

    notif_result = await db.execute(
        select(AdminNotification).where(AdminNotification.type == "payment_submitted")
    )
    assert notif_result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_submit_payment_non_pending_rejected(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=300.0)
    await db.commit()

    await _add_to_cart(client, variant.id)
    create_res = await _create_order(client)
    order_id = create_res.json()["order_id"]

    # Cancel first
    await client.post(f"{ORDERS_URL}/{order_id}/cancel", json={})

    res = await client.post(f"{ORDERS_URL}/{order_id}/payment-submission", json={
        "transfer_amount": 420.0,
        "transfer_date": "2026-04-23",
        "transfer_time": "14:30:00",
        "account_last5": "12345",
    })
    assert res.status_code == 400


# ── Cancel Order Tests ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cancel_pending_order(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=300.0)
    await db.commit()

    await _add_to_cart(client, variant.id)
    create_res = await _create_order(client)
    order_id = create_res.json()["order_id"]

    res = await client.post(f"{ORDERS_URL}/{order_id}/cancel", json={})
    assert res.status_code == 200

    order_res = await db.execute(select(Order).where(Order.id == order_id))
    order = order_res.scalar_one()
    assert order.status == OrderStatusEnum.cancelled


@pytest.mark.asyncio
async def test_cancel_paid_order_rejected(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _make_admin(db)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=300.0)
    await db.commit()

    await _login_customer(client)
    await _add_to_cart(client, variant.id)
    create_res = await _create_order(client)
    order_id = create_res.json()["order_id"]

    # Mark as paid via admin
    await _login_admin(client)
    await client.patch(f"{ADMIN_ORDERS_URL}/{order_id}/status", json={"status": "paid"})

    await _login_customer(client)
    res = await client.post(f"{ORDERS_URL}/{order_id}/cancel", json={})
    assert res.status_code == 400


# ── Confirm Received Tests ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_confirm_received_success(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _make_admin(db)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=300.0)
    await db.commit()

    await _login_customer(client)
    await _add_to_cart(client, variant.id)
    create_res = await _create_order(client)
    order_id = create_res.json()["order_id"]

    # Admin: paid → create shipment (which marks as shipped)
    await _login_admin(client)
    await client.patch(f"{ADMIN_ORDERS_URL}/{order_id}/status", json={"status": "paid"})
    await client.post(
        f"{ADMIN_ORDERS_URL}/{order_id}/shipments", json={"shipment_type": "fulfilled"}
    )

    await _login_customer(client)
    res = await client.post(f"{ORDERS_URL}/{order_id}/confirm-received")
    assert res.status_code == 200, f"got {res.status_code}: {res.text}"

    order_res = await db.execute(select(Order).where(Order.id == order_id))
    order = order_res.scalar_one()
    assert order.status == OrderStatusEnum.completed


@pytest.mark.asyncio
async def test_confirm_received_non_shipped_rejected(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _login_customer(client)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=300.0)
    await db.commit()

    await _add_to_cart(client, variant.id)
    create_res = await _create_order(client)
    order_id = create_res.json()["order_id"]

    res = await client.post(f"{ORDERS_URL}/{order_id}/confirm-received")
    assert res.status_code == 400


# ── Confirm Refund Tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_confirm_refund_success(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _make_admin(db)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=300.0)
    await db.commit()

    await _login_customer(client)
    await _add_to_cart(client, variant.id)
    create_res = await _create_order(client)
    order_id = create_res.json()["order_id"]

    await _login_admin(client)
    await client.patch(f"{ADMIN_ORDERS_URL}/{order_id}/status", json={"status": "paid"})
    await client.patch(
        f"{ADMIN_ORDERS_URL}/{order_id}/status", json={"status": "refund_processing"}
    )

    # Get order items for refund
    order_res = await db.execute(select(OrderItem).where(OrderItem.order_id == order_id))
    items = order_res.scalars().all()
    item_ids = [str(i.id) for i in items]

    await client.post(f"{ADMIN_ORDERS_URL}/{order_id}/refund", json={
        "refund_amount": 420.0,
        "returned_item_ids": item_ids,
    })

    await _login_customer(client)
    res = await client.post(f"{ORDERS_URL}/{order_id}/confirm-refund")
    assert res.status_code == 204


@pytest.mark.asyncio
async def test_confirm_refund_already_confirmed_rejected(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _make_admin(db)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=300.0)
    await db.commit()

    await _login_customer(client)
    await _add_to_cart(client, variant.id)
    create_res = await _create_order(client)
    order_id = create_res.json()["order_id"]

    await _login_admin(client)
    await client.patch(f"{ADMIN_ORDERS_URL}/{order_id}/status", json={"status": "paid"})
    await client.patch(
        f"{ADMIN_ORDERS_URL}/{order_id}/status", json={"status": "refund_processing"}
    )

    order_res = await db.execute(select(OrderItem).where(OrderItem.order_id == order_id))
    items = order_res.scalars().all()
    item_ids = [str(i.id) for i in items]
    await client.post(f"{ADMIN_ORDERS_URL}/{order_id}/refund", json={
        "refund_amount": 420.0,
        "returned_item_ids": item_ids,
    })

    await _login_customer(client)
    await client.post(f"{ORDERS_URL}/{order_id}/confirm-refund")
    # Second confirm
    res = await client.post(f"{ORDERS_URL}/{order_id}/confirm-refund")
    assert res.status_code == 400


# ── Admin Order Tests ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_list_orders_with_search(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _make_admin(db)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=300.0)
    await db.commit()

    await _login_customer(client)
    await _add_to_cart(client, variant.id)
    create_res = await _create_order(client)
    order_number = create_res.json()["order_number"]

    await _login_admin(client)
    res = await client.get(f"{ADMIN_ORDERS_URL}?search={order_number}")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] >= 1
    assert any(o["order_number"] == order_number for o in data["items"])


@pytest.mark.asyncio
async def test_admin_get_order_detail(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _make_admin(db)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=300.0)
    await db.commit()

    await _login_customer(client)
    await _add_to_cart(client, variant.id)
    create_res = await _create_order(client)
    order_id = create_res.json()["order_id"]

    await _login_admin(client)
    res = await client.get(f"{ADMIN_ORDERS_URL}/{order_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == order_id
    assert "user_name" in data
    assert "admin_notes" in data


@pytest.mark.asyncio
async def test_admin_status_to_paid_creates_production_progress(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _make_admin(db)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=300.0)
    await db.commit()

    await _login_customer(client)
    await _add_to_cart(client, variant.id)
    create_res = await _create_order(client)
    order_id = create_res.json()["order_id"]

    await _login_admin(client)
    res = await client.patch(f"{ADMIN_ORDERS_URL}/{order_id}/status", json={"status": "paid"})
    assert res.status_code == 200
    assert res.json()["status"] == "paid"

    prog_result = await db.execute(
        select(ProductionProgress)
        .join(OrderItem, ProductionProgress.order_item_id == OrderItem.id)
        .where(OrderItem.order_id == order_id)
    )
    assert prog_result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_admin_cancel_pending_order(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _make_admin(db)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=300.0)
    await db.commit()

    await _login_customer(client)
    await _add_to_cart(client, variant.id)
    create_res = await _create_order(client)
    order_id = create_res.json()["order_id"]

    await _login_admin(client)
    res = await client.patch(f"{ADMIN_ORDERS_URL}/{order_id}/status", json={
        "status": "cancelled",
        "admin_notes": "Admin cancel test",
    })
    assert res.status_code == 200
    assert res.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_admin_cancel_paid_order_rejected(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _make_admin(db)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=300.0)
    await db.commit()

    await _login_customer(client)
    await _add_to_cart(client, variant.id)
    create_res = await _create_order(client)
    order_id = create_res.json()["order_id"]

    await _login_admin(client)
    await client.patch(f"{ADMIN_ORDERS_URL}/{order_id}/status", json={"status": "paid"})

    res = await client.patch(f"{ADMIN_ORDERS_URL}/{order_id}/status", json={"status": "cancelled"})
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_admin_status_to_refund_processing(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _make_admin(db)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=300.0)
    await db.commit()

    await _login_customer(client)
    await _add_to_cart(client, variant.id)
    create_res = await _create_order(client)
    order_id = create_res.json()["order_id"]

    await _login_admin(client)
    await client.patch(f"{ADMIN_ORDERS_URL}/{order_id}/status", json={"status": "paid"})
    res = await client.patch(
        f"{ADMIN_ORDERS_URL}/{order_id}/status", json={"status": "refund_processing"}
    )
    assert res.status_code == 200
    assert res.json()["status"] == "refund_processing"


@pytest.mark.asyncio
async def test_create_shipment_ecpay_mock(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _make_admin(db)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=300.0)
    await db.commit()

    await _login_customer(client)
    await _add_to_cart(client, variant.id)
    create_res = await _create_order(client)
    order_id = create_res.json()["order_id"]

    await _login_admin(client)
    await client.patch(f"{ADMIN_ORDERS_URL}/{order_id}/status", json={"status": "paid"})

    res = await client.post(
        f"{ADMIN_ORDERS_URL}/{order_id}/shipments", json={"shipment_type": "fulfilled"}
    )
    assert res.status_code == 201
    data = res.json()
    assert data["tracking_number"].startswith("MOCK-")

    order_res = await db.execute(select(Order).where(Order.id == order_id))
    order = order_res.scalar_one()
    assert order.status == OrderStatusEnum.shipped


@pytest.mark.asyncio
async def test_update_production_progress_manufacturing(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _make_admin(db)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=300.0)
    await db.commit()

    await _login_customer(client)
    await _add_to_cart(client, variant.id)
    create_res = await _create_order(client)
    order_id = create_res.json()["order_id"]

    await _login_admin(client)
    await client.patch(f"{ADMIN_ORDERS_URL}/{order_id}/status", json={"status": "paid"})

    prog_result = await db.execute(
        select(ProductionProgress)
        .join(OrderItem, ProductionProgress.order_item_id == OrderItem.id)
        .where(OrderItem.order_id == order_id)
    )
    progress = prog_result.scalar_one()

    res = await client.patch(
        f"{ADMIN_ORDERS_URL}/{order_id}/production-progress/{progress.id}",
        json={"status": "manufacturing"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "manufacturing"
    assert body["order_item_id"] == str(progress.order_item_id)
    assert "updated_at" in body


@pytest.mark.asyncio
async def test_update_production_progress_shipped_rejected(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _make_admin(db)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=300.0)
    await db.commit()

    await _login_customer(client)
    await _add_to_cart(client, variant.id)
    create_res = await _create_order(client)
    order_id = create_res.json()["order_id"]

    await _login_admin(client)
    await client.patch(f"{ADMIN_ORDERS_URL}/{order_id}/status", json={"status": "paid"})

    prog_result = await db.execute(
        select(ProductionProgress)
        .join(OrderItem, ProductionProgress.order_item_id == OrderItem.id)
        .where(OrderItem.order_id == order_id)
    )
    progress = prog_result.scalar_one()

    res = await client.patch(
        f"{ADMIN_ORDERS_URL}/{order_id}/production-progress/{progress.id}",
        json={"status": "shipped"},
    )
    # "shipped" rejected at schema level — not in Literal
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_full_refund(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _make_admin(db)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=300.0)
    await db.commit()

    await _login_customer(client)
    await _add_to_cart(client, variant.id)
    create_res = await _create_order(client)
    order_id = create_res.json()["order_id"]
    total = create_res.json()["total"]

    await _login_admin(client)
    await client.patch(f"{ADMIN_ORDERS_URL}/{order_id}/status", json={"status": "paid"})
    await client.patch(
        f"{ADMIN_ORDERS_URL}/{order_id}/status", json={"status": "refund_processing"}
    )

    item_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order_id))
    items = item_result.scalars().all()
    item_ids = [str(i.id) for i in items]

    res = await client.post(f"{ADMIN_ORDERS_URL}/{order_id}/refund", json={
        "refund_amount": total,
        "returned_item_ids": item_ids,
    })
    assert res.status_code == 200
    assert res.json()["status"] == "refunded"


@pytest.mark.asyncio
async def test_partial_refund(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _make_admin(db)
    job = await _make_production_job(db)
    _, v1 = await _make_product_and_variant(db, job.id, price=300.0)
    _, v2 = await _make_product_and_variant(db, job.id, price=200.0)
    await db.commit()

    await _login_customer(client)
    await _add_to_cart(client, v1.id)
    await _add_to_cart(client, v2.id)
    create_res = await _create_order(client)
    order_id = create_res.json()["order_id"]

    await _login_admin(client)
    await client.patch(f"{ADMIN_ORDERS_URL}/{order_id}/status", json={"status": "paid"})
    await client.patch(
        f"{ADMIN_ORDERS_URL}/{order_id}/status", json={"status": "refund_processing"}
    )

    item_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order_id))
    items = item_result.scalars().all()
    # Return only first item
    one_item_id = [str(items[0].id)]

    res = await client.post(f"{ADMIN_ORDERS_URL}/{order_id}/refund", json={
        "refund_amount": 300.0,
        "returned_item_ids": one_item_id,
    })
    assert res.status_code == 200
    assert res.json()["status"] == "partially_refunded"


@pytest.mark.asyncio
async def test_refund_exceeds_total_rejected(client, db):
    """Admin cannot refund more than the order total."""
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _make_admin(db)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=300.0)
    await db.commit()

    await _login_customer(client)
    await _add_to_cart(client, variant.id)
    create_res = await _create_order(client)
    order_id = create_res.json()["order_id"]
    order_total = create_res.json()["total"]

    await _login_admin(client)
    await client.patch(f"{ADMIN_ORDERS_URL}/{order_id}/status", json={"status": "paid"})
    await client.patch(
        f"{ADMIN_ORDERS_URL}/{order_id}/status", json={"status": "refund_processing"}
    )

    item_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order_id))
    items = item_result.scalars().all()
    item_ids = [str(i.id) for i in items]

    res = await client.post(f"{ADMIN_ORDERS_URL}/{order_id}/refund", json={
        "refund_amount": order_total + 1000.0,
        "returned_item_ids": item_ids,
    })
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_flag_payment_submission(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _make_admin(db)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=300.0)
    await db.commit()

    await _login_customer(client)
    await _add_to_cart(client, variant.id)
    create_res = await _create_order(client)
    order_id = create_res.json()["order_id"]

    await client.post(f"{ORDERS_URL}/{order_id}/payment-submission", json={
        "transfer_amount": 420.0,
        "transfer_date": "2026-04-23",
        "transfer_time": "14:30:00",
        "account_last5": "12345",
    })

    sub_result = await db.execute(
        select(PaymentSubmission).where(PaymentSubmission.order_id == order_id)
    )
    sub = sub_result.scalar_one()

    await _login_admin(client)
    res = await client.patch(
        f"{ADMIN_ORDERS_URL}/{order_id}/payment-submissions/{sub.id}/flag",
        json={"is_flagged": True, "admin_note": "金額有誤"},
    )
    assert res.status_code == 200
    assert "payment_deadline" in res.json()


@pytest.mark.asyncio
async def test_update_admin_notes(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _make_admin(db)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=300.0)
    await db.commit()

    await _login_customer(client)
    await _add_to_cart(client, variant.id)
    create_res = await _create_order(client)
    order_id = create_res.json()["order_id"]

    await _login_admin(client)
    res = await client.patch(f"{ADMIN_ORDERS_URL}/{order_id}/admin-notes", json={
        "admin_notes": "需確認收款",
    })
    assert res.status_code == 200
    assert res.json()["admin_notes"] == "需確認收款"


# ── Webhook Tests ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ecpay_webhook_delivered_completes_order(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _make_admin(db)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=300.0)
    await db.commit()

    await _login_customer(client)
    await _add_to_cart(client, variant.id)
    create_res = await _create_order(client)
    order_id = create_res.json()["order_id"]

    await _login_admin(client)
    await client.patch(f"{ADMIN_ORDERS_URL}/{order_id}/status", json={"status": "paid"})
    ship_res = await client.post(
        f"{ADMIN_ORDERS_URL}/{order_id}/shipments", json={"shipment_type": "fulfilled"}
    )
    ecpay_logistics_id = ship_res.json()["ecpay_logistics_id"]

    res = await client.post("/api/v1/webhooks/ecpay", data={
        "AllPayLogisticsID": ecpay_logistics_id,
        "RtnCode": "3",
        "RtnMsg": "已投遞",
    })
    assert res.status_code == 200
    assert res.text == "1|OK"

    order_res = await db.execute(select(Order).where(Order.id == order_id))
    order = order_res.scalar_one()
    assert order.status == OrderStatusEnum.completed


@pytest.mark.asyncio
async def test_ecpay_webhook_other_status_creates_notification(client, db):
    await _seed_system_settings(db)
    await _make_customer(client, db)
    await _make_admin(db)
    job = await _make_production_job(db)
    _, variant = await _make_product_and_variant(db, job.id, price=300.0)
    await db.commit()

    await _login_customer(client)
    await _add_to_cart(client, variant.id)
    create_res = await _create_order(client)
    order_id = create_res.json()["order_id"]

    await _login_admin(client)
    await client.patch(f"{ADMIN_ORDERS_URL}/{order_id}/status", json={"status": "paid"})
    ship_res = await client.post(
        f"{ADMIN_ORDERS_URL}/{order_id}/shipments", json={"shipment_type": "fulfilled"}
    )
    ecpay_logistics_id = ship_res.json()["ecpay_logistics_id"]

    res = await client.post("/api/v1/webhooks/ecpay", data={
        "AllPayLogisticsID": ecpay_logistics_id,
        "RtnCode": "99",
        "RtnMsg": "派送中",
    })
    assert res.status_code == 200

    notif_result = await db.execute(
        select(AdminNotification).where(AdminNotification.type == "ecpay_status")
    )
    assert notif_result.scalar_one_or_none() is not None
