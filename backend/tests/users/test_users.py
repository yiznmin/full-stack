import pytest
from httpx import AsyncClient
from sqlalchemy import select

from auth.models import EmailVerificationToken, TokenTypeEnum, User

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
ME_URL = "/api/v1/users/me"
CHANGE_PW_URL = "/api/v1/users/me/change-password"
EMAIL_CHANGE_URL = "/api/v1/users/me/request-email-change"
SHIPPING_URL = "/api/v1/users/me/shipping-profiles"

VALID_USER = {"name": "測試用戶", "email": "user@example.com", "password": "testpass123"}
VALID_PASSWORD = "testpass123"

HOME_PROFILE = {
    "shipping_type": "home",
    "recipient_name": "王小明",
    "phone": "0912345678",
    "city": "台北市",
    "district": "大安區",
    "address_detail": "信義路四段1號",
    "is_default": False,
}

SEVEN_PROFILE = {
    "shipping_type": "seven_eleven",
    "recipient_name": "王小明",
    "phone": "0912345678",
    "store_id": "123456",
    "store_name": "7-11 信義門市",
    "is_default": False,
}


async def _make_verified_user(client: AsyncClient, db, email=None, password=None):
    payload = {**VALID_USER}
    if email:
        payload["email"] = email
    if password:
        payload["password"] = password
    await client.post(REGISTER_URL, json=payload)
    result = await db.execute(select(User).where(User.email == payload["email"]))
    user = result.scalar_one()
    user.is_email_verified = True
    await db.commit()
    return user


async def _login(client: AsyncClient, email=None, password=None):
    res = await client.post(LOGIN_URL, json={
        "email": email or VALID_USER["email"],
        "password": password or VALID_PASSWORD,
    })
    if "access_token" in res.cookies:
        client.cookies.set("access_token", res.cookies["access_token"])
    return res


# ── PATCH /users/me ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_patch_profile_name(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    res = await client.patch(ME_URL, json={"name": "新名字測試"})
    assert res.status_code == 200
    assert res.json()["name"] == "新名字測試"


@pytest.mark.asyncio
async def test_patch_profile_gender_and_birthday(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    res = await client.patch(ME_URL, json={"gender": "male", "birthday": "1990-05-15"})
    assert res.status_code == 200
    data = res.json()
    assert data["gender"] == "male"
    assert data["birthday"] == "1990-05-15"


@pytest.mark.asyncio
async def test_patch_profile_clear_gender(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    await client.patch(ME_URL, json={"gender": "male"})
    res = await client.patch(ME_URL, json={"gender": None})
    assert res.status_code == 200
    assert res.json()["gender"] is None


@pytest.mark.asyncio
async def test_patch_profile_unset_fields_unchanged(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    await client.patch(ME_URL, json={"gender": "female"})
    res = await client.patch(ME_URL, json={"name": "只改名字"})
    assert res.status_code == 200
    assert res.json()["gender"] == "female"


@pytest.mark.asyncio
async def test_patch_profile_name_too_short(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    res = await client.patch(ME_URL, json={"name": "ab"})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_patch_profile_unauthenticated(client: AsyncClient, db):
    res = await client.patch(ME_URL, json={"name": "無登入"})
    assert res.status_code == 401


# ── POST /users/me/change-password ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_change_password_success(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    res = await client.post(CHANGE_PW_URL, json={
        "old_password": VALID_PASSWORD,
        "new_password": "newpassword99",
    })
    assert res.status_code == 204
    login_res = await _login(client, password="newpassword99")
    assert login_res.status_code == 200


@pytest.mark.asyncio
async def test_change_password_wrong_old(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    res = await client.post(CHANGE_PW_URL, json={
        "old_password": "wrongpassword1",
        "new_password": "newpassword99",
    })
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_change_password_new_too_short(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    res = await client.post(CHANGE_PW_URL, json={
        "old_password": VALID_PASSWORD,
        "new_password": "short1",
    })
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_change_password_unauthenticated(client: AsyncClient, db):
    res = await client.post(CHANGE_PW_URL, json={
        "old_password": VALID_PASSWORD,
        "new_password": "newpassword99",
    })
    assert res.status_code == 401


# ── POST /users/me/request-email-change ───────────────────────────────────────

@pytest.mark.asyncio
async def test_request_email_change_success(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    res = await client.post(EMAIL_CHANGE_URL, json={"new_email": "new@example.com"})
    assert res.status_code == 200
    result = await db.execute(select(User).where(User.email == VALID_USER["email"]))
    user = result.scalar_one()
    assert user.pending_email == "new@example.com"


@pytest.mark.asyncio
async def test_request_email_change_same_as_current(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    res = await client.post(EMAIL_CHANGE_URL, json={"new_email": VALID_USER["email"]})
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_request_email_change_same_as_pending(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    await client.post(EMAIL_CHANGE_URL, json={"new_email": "pending@example.com"})
    res = await client.post(EMAIL_CHANGE_URL, json={"new_email": "pending@example.com"})
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_request_email_change_conflict(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _make_verified_user(client, db, email="other@example.com")
    await _login(client)
    res = await client.post(EMAIL_CHANGE_URL, json={"new_email": "other@example.com"})
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_request_email_change_invalidates_old_token(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    await client.post(EMAIL_CHANGE_URL, json={"new_email": "first@example.com"})
    await client.post(EMAIL_CHANGE_URL, json={"new_email": "second@example.com"})

    result = await db.execute(
        select(EmailVerificationToken)
        .join(User, User.id == EmailVerificationToken.user_id)
        .where(
            User.email == VALID_USER["email"],
            EmailVerificationToken.token_type == TokenTypeEnum.email_change,
        )
        .order_by(EmailVerificationToken.created_at)
    )
    tokens = result.scalars().all()
    assert len(tokens) == 2
    assert tokens[0].used_at is not None
    assert tokens[1].used_at is None


@pytest.mark.asyncio
async def test_request_email_change_unauthenticated(client: AsyncClient, db):
    res = await client.post(EMAIL_CHANGE_URL, json={"new_email": "new@example.com"})
    assert res.status_code == 401


# ── GET /users/me/shipping-profiles ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_shipping_profiles_empty(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    res = await client.get(SHIPPING_URL)
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_list_shipping_profiles_default_first(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    await client.post(SHIPPING_URL, json=HOME_PROFILE)
    await client.post(SHIPPING_URL, json={**SEVEN_PROFILE, "is_default": True})
    res = await client.get(SHIPPING_URL)
    assert res.status_code == 200
    data = res.json()
    assert data[0]["is_default"] is True


# ── POST /users/me/shipping-profiles ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_home_profile(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    res = await client.post(SHIPPING_URL, json=HOME_PROFILE)
    assert res.status_code == 201
    data = res.json()
    assert data["shipping_type"] == "home"
    assert data["city"] == "台北市"


@pytest.mark.asyncio
async def test_create_seven_eleven_profile(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    res = await client.post(SHIPPING_URL, json=SEVEN_PROFILE)
    assert res.status_code == 201
    assert res.json()["shipping_type"] == "seven_eleven"


@pytest.mark.asyncio
async def test_create_home_missing_city(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    bad = {**HOME_PROFILE}
    del bad["city"]
    res = await client.post(SHIPPING_URL, json=bad)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_seven_eleven_missing_store_id(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    bad = {**SEVEN_PROFILE}
    del bad["store_id"]
    res = await client.post(SHIPPING_URL, json=bad)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_profile_invalid_phone(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    res = await client.post(SHIPPING_URL, json={**HOME_PROFILE, "phone": "1234567890"})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_create_profile_sets_default_clears_old(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    r1 = await client.post(SHIPPING_URL, json={**HOME_PROFILE, "is_default": True})
    first_id = r1.json()["id"]
    await client.post(SHIPPING_URL, json={**SEVEN_PROFILE, "is_default": True})
    res = await client.get(SHIPPING_URL)
    profiles = {p["id"]: p for p in res.json()}
    assert profiles[first_id]["is_default"] is False


@pytest.mark.asyncio
async def test_create_profile_limit(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    for _ in range(10):
        await client.post(SHIPPING_URL, json=HOME_PROFILE)
    res = await client.post(SHIPPING_URL, json=HOME_PROFILE)
    assert res.status_code == 400


# ── PUT /users/me/shipping-profiles/{id} ──────────────────────────────────────

@pytest.mark.asyncio
async def test_update_profile(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    r = await client.post(SHIPPING_URL, json=HOME_PROFILE)
    pid = r.json()["id"]
    res = await client.put(f"{SHIPPING_URL}/{pid}", json={**HOME_PROFILE, "city": "新北市"})
    assert res.status_code == 200
    assert res.json()["city"] == "新北市"


@pytest.mark.asyncio
async def test_update_profile_not_found(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    fake_id = "00000000-0000-0000-0000-000000000000"
    res = await client.put(f"{SHIPPING_URL}/{fake_id}", json=HOME_PROFILE)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_update_profile_other_user(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    r = await client.post(SHIPPING_URL, json=HOME_PROFILE)
    pid = r.json()["id"]

    await _make_verified_user(client, db, email="other2@example.com")
    await _login(client, email="other2@example.com")
    res = await client.put(f"{SHIPPING_URL}/{pid}", json=HOME_PROFILE)
    assert res.status_code == 404


# ── DELETE /users/me/shipping-profiles/{id} ───────────────────────────────────

@pytest.mark.asyncio
async def test_delete_profile(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    r = await client.post(SHIPPING_URL, json=HOME_PROFILE)
    pid = r.json()["id"]
    res = await client.delete(f"{SHIPPING_URL}/{pid}")
    assert res.status_code == 204
    list_res = await client.get(SHIPPING_URL)
    assert all(p["id"] != pid for p in list_res.json())


@pytest.mark.asyncio
async def test_delete_profile_not_found(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    res = await client.delete(f"{SHIPPING_URL}/00000000-0000-0000-0000-000000000000")
    assert res.status_code == 404


# ── PATCH /users/me/shipping-profiles/{id}/set-default ────────────────────────

@pytest.mark.asyncio
async def test_set_default(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    r1 = await client.post(SHIPPING_URL, json={**HOME_PROFILE, "is_default": True})
    r2 = await client.post(SHIPPING_URL, json=SEVEN_PROFILE)
    pid2 = r2.json()["id"]

    res = await client.patch(f"{SHIPPING_URL}/{pid2}/set-default")
    assert res.status_code == 200
    assert res.json()["is_default"] is True

    list_res = await client.get(SHIPPING_URL)
    profiles = {p["id"]: p for p in list_res.json()}
    assert profiles[r1.json()["id"]]["is_default"] is False


@pytest.mark.asyncio
async def test_set_default_not_found(client: AsyncClient, db):
    await _make_verified_user(client, db)
    await _login(client)
    res = await client.patch(f"{SHIPPING_URL}/00000000-0000-0000-0000-000000000000/set-default")
    assert res.status_code == 404
