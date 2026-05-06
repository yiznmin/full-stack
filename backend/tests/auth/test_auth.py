from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from auth.models import EmailVerificationToken, PasswordResetToken, RoleEnum, User
from auth.service import _hash_password, _hash_token, cleanup_unverified_users

REGISTER_URL = "/api/v1/auth/register"
LOGIN_URL = "/api/v1/auth/login"
LOGOUT_URL = "/api/v1/auth/logout"
ME_URL = "/api/v1/auth/me"
VERIFY_URL = "/api/v1/auth/verify-email"
RESEND_URL = "/api/v1/auth/resend-verification"
FORGOT_URL = "/api/v1/auth/forgot-password"
RESET_URL = "/api/v1/auth/reset-password"
ADMIN_LOGIN_URL = "/api/v1/admin/auth/login"

VALID_USER = {"name": "測試用戶", "email": "test@example.com", "password": "testpass123"}
VALID_PASSWORD = "testpass123"


async def _register_and_verify(client: AsyncClient, db, email=None, password=None):
    """Helper：註冊並完成 email 驗證，回傳 user。"""
    payload = {**VALID_USER}
    if email:
        payload["email"] = email
    if password:
        payload["password"] = password

    await client.post(REGISTER_URL, json=payload)

    # Directly update user to verified for test convenience (token is hashed in DB)
    result2 = await db.execute(select(User).where(User.email == payload["email"]))
    user = result2.scalar_one()
    user.is_email_verified = True
    await db.commit()
    return user


# ── Register ───────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_success(client: AsyncClient, db):
    res = await client.post(REGISTER_URL, json=VALID_USER)
    assert res.status_code == 201
    assert res.json()["message"] == "驗證信已寄出"

    result = await db.execute(select(User).where(User.email == VALID_USER["email"]))
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.role == "customer"
    assert user.is_email_verified is False


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, db):
    await client.post(REGISTER_URL, json=VALID_USER)
    res = await client.post(REGISTER_URL, json=VALID_USER)
    assert res.status_code == 409


@pytest.mark.asyncio
async def test_register_password_too_short(client: AsyncClient, db):
    res = await client.post(REGISTER_URL, json={**VALID_USER, "password": "abc123"})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_register_password_no_letter(client: AsyncClient, db):
    res = await client.post(REGISTER_URL, json={**VALID_USER, "password": "1234567890"})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_register_password_no_digit(client: AsyncClient, db):
    res = await client.post(REGISTER_URL, json={**VALID_USER, "password": "abcdefghij"})
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_register_name_too_short(client: AsyncClient, db):
    res = await client.post(REGISTER_URL, json={**VALID_USER, "name": "ab"})
    assert res.status_code == 422


# ── Login ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_unverified_email(client: AsyncClient, db):
    await client.post(REGISTER_URL, json=VALID_USER)
    res = await client.post(
        LOGIN_URL, json={"email": VALID_USER["email"], "password": VALID_PASSWORD}
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient, db):
    await _register_and_verify(client, db)
    res = await client.post(
        LOGIN_URL, json={"email": VALID_USER["email"], "password": "wrongpass999"}
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_email(client: AsyncClient, db):
    res = await client.post(
        LOGIN_URL, json={"email": "nobody@example.com", "password": VALID_PASSWORD}
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, db):
    await _register_and_verify(client, db)
    res = await client.post(
        LOGIN_URL, json={"email": VALID_USER["email"], "password": VALID_PASSWORD}
    )
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "customer"
    assert data["name"] == VALID_USER["name"]
    assert "access_token" in res.cookies


@pytest.mark.asyncio
async def test_login_disabled_account(client: AsyncClient, db):
    user = await _register_and_verify(client, db)
    user.is_active = False
    await db.commit()

    res = await client.post(
        LOGIN_URL, json={"email": VALID_USER["email"], "password": VALID_PASSWORD}
    )
    assert res.status_code == 403


# ── Verify Email ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_verify_email_signup_success(client: AsyncClient, db):
    await client.post(REGISTER_URL, json=VALID_USER)

    result = await db.execute(
        select(EmailVerificationToken)
        .join(User, User.id == EmailVerificationToken.user_id)
        .where(User.email == VALID_USER["email"])
    )
    token_row = result.scalar_one()

    # We need the plain token - re-create it to simulate the email link
    # For testing: directly set a known token hash
    import secrets

    from auth.service import _hash_token
    plain = secrets.token_urlsafe(32)
    token_row.token = _hash_token(plain)
    await db.commit()

    res = await client.post(VERIFY_URL, json={"token": plain})
    assert res.status_code == 200
    assert res.json()["token_type"] == "signup"

    await db.refresh(token_row)
    result2 = await db.execute(select(User).where(User.email == VALID_USER["email"]))
    user = result2.scalar_one()
    assert user.is_email_verified is True


@pytest.mark.asyncio
async def test_verify_email_invalid_token(client: AsyncClient, db):
    res = await client.post(VERIFY_URL, json={"token": "invalidtoken"})
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_verify_email_used_token(client: AsyncClient, db):
    import secrets
    from datetime import datetime
    await client.post(REGISTER_URL, json=VALID_USER)

    result = await db.execute(
        select(EmailVerificationToken)
        .join(User, User.id == EmailVerificationToken.user_id)
        .where(User.email == VALID_USER["email"])
    )
    token_row = result.scalar_one()
    plain = secrets.token_urlsafe(32)
    token_row.token = _hash_token(plain)
    token_row.used_at = datetime.now(UTC)
    await db.commit()

    res = await client.post(VERIFY_URL, json={"token": plain})
    assert res.status_code == 400


# ── Forgot / Reset Password ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_forgot_password_nonexistent_email(client: AsyncClient, db):
    res = await client.post(FORGOT_URL, json={"email": "nobody@example.com"})
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_success(client: AsyncClient, db):
    import secrets
    user = await _register_and_verify(client, db)

    plain = secrets.token_urlsafe(32)
    from datetime import datetime, timedelta
    token = PasswordResetToken(
        user_id=user.id,
        token=_hash_token(plain),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db.add(token)
    await db.commit()

    res = await client.post(RESET_URL, json={"token": plain, "new_password": "newpass12345"})
    assert res.status_code == 200

    login_res = await client.post(
        LOGIN_URL, json={"email": VALID_USER["email"], "password": "newpass12345"}
    )
    assert login_res.status_code == 200


@pytest.mark.asyncio
async def test_reset_password_invalid_token(client: AsyncClient, db):
    res = await client.post(RESET_URL, json={"token": "badtoken", "new_password": "newpass12345"})
    assert res.status_code == 400


# ── Admin Login ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_verify_email_change_expired_token(client: AsyncClient, db):
    import secrets
    from datetime import datetime, timedelta
    user = await _register_and_verify(client, db)
    user.pending_email = "changed@example.com"
    await db.commit()

    plain = secrets.token_urlsafe(32)
    from auth.models import TokenTypeEnum
    token = EmailVerificationToken(
        user_id=user.id,
        token=_hash_token(plain),
        token_type=TokenTypeEnum.email_change,
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    db.add(token)
    await db.commit()

    res = await client.post(VERIFY_URL, json={"token": plain})
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_verify_email_change_success(client: AsyncClient, db):
    import secrets
    from datetime import datetime, timedelta
    user = await _register_and_verify(client, db)
    user.pending_email = "changed@example.com"
    await db.commit()

    plain = secrets.token_urlsafe(32)
    from auth.models import TokenTypeEnum
    token = EmailVerificationToken(
        user_id=user.id,
        token=_hash_token(plain),
        token_type=TokenTypeEnum.email_change,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    db.add(token)
    await db.commit()

    res = await client.post(VERIFY_URL, json={"token": plain})
    assert res.status_code == 200
    assert res.json()["token_type"] == "email_change"

    await db.refresh(user)
    assert user.email == "changed@example.com"
    assert user.pending_email is None


@pytest.mark.asyncio
async def test_verify_email_change_old_email_cannot_login(client: AsyncClient, db):
    import secrets
    from datetime import datetime, timedelta
    user = await _register_and_verify(client, db)
    old_email = user.email
    user.pending_email = "changed2@example.com"
    await db.commit()

    plain = secrets.token_urlsafe(32)
    from auth.models import TokenTypeEnum
    token = EmailVerificationToken(
        user_id=user.id,
        token=_hash_token(plain),
        token_type=TokenTypeEnum.email_change,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    db.add(token)
    await db.commit()

    await client.post(VERIFY_URL, json={"token": plain})

    res = await client.post(LOGIN_URL, json={"email": old_email, "password": VALID_PASSWORD})
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_verify_email_change_new_email_can_login(client: AsyncClient, db):
    import secrets
    from datetime import datetime, timedelta
    user = await _register_and_verify(client, db)
    user.pending_email = "changed3@example.com"
    await db.commit()

    plain = secrets.token_urlsafe(32)
    from auth.models import TokenTypeEnum
    token = EmailVerificationToken(
        user_id=user.id,
        token=_hash_token(plain),
        token_type=TokenTypeEnum.email_change,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    db.add(token)
    await db.commit()

    await client.post(VERIFY_URL, json={"token": plain})

    res = await client.post(
        LOGIN_URL, json={"email": "changed3@example.com", "password": VALID_PASSWORD}
    )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_verify_email_change_used_token(client: AsyncClient, db):
    import secrets
    from datetime import datetime, timedelta
    user = await _register_and_verify(client, db)
    user.pending_email = "used@example.com"
    await db.commit()

    plain = secrets.token_urlsafe(32)
    from auth.models import TokenTypeEnum
    token = EmailVerificationToken(
        user_id=user.id,
        token=_hash_token(plain),
        token_type=TokenTypeEnum.email_change,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
        used_at=datetime.now(UTC),
    )
    db.add(token)
    await db.commit()

    res = await client.post(VERIFY_URL, json={"token": plain})
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_admin_login_with_customer_account(client: AsyncClient, db):
    await _register_and_verify(client, db)
    res = await client.post(
        ADMIN_LOGIN_URL, json={"email": VALID_USER["email"], "password": VALID_PASSWORD}
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_login_success(client: AsyncClient, db):
    import bcrypt
    admin = User(
        name="Admin",
        email="admin@test.com",
        password_hash=bcrypt.hashpw(b"adminpass123", bcrypt.gensalt()).decode(),
        role="admin",
        is_active=True,
        is_email_verified=True,
    )
    db.add(admin)
    await db.commit()

    res = await client.post(
        ADMIN_LOGIN_URL, json={"email": "admin@test.com", "password": "adminpass123"}
    )
    assert res.status_code == 200
    assert res.json()["role"] == "admin"
    assert "access_token" in res.cookies


# ── Cleanup unverified users ───────────────────────────────────────────────────

async def _make_user(db, email: str, *, verified: bool, age_hours: int, role=RoleEnum.customer):
    user = User(
        name=f"u_{email}",
        email=email,
        password_hash=_hash_password("p4ssw0rd_xyz"),
        role=role,
        is_email_verified=verified,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    # 強制 created_at 為過去時間（service 比對用 created_at）
    user.created_at = datetime.now(UTC) - timedelta(hours=age_hours)
    await db.commit()
    return user


@pytest.mark.asyncio
async def test_cleanup_deletes_old_unverified_customer(db):
    user = await _make_user(db, "stale@test.com", verified=False, age_hours=30)
    user_id = user.id

    deleted = await cleanup_unverified_users(db, grace_hours=25)

    assert deleted == 1
    result = await db.execute(select(User).where(User.id == user_id))
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_cleanup_skips_recent_unverified_customer(db):
    user = await _make_user(db, "fresh@test.com", verified=False, age_hours=10)

    deleted = await cleanup_unverified_users(db, grace_hours=25)

    assert deleted == 0
    result = await db.execute(select(User).where(User.id == user.id))
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_cleanup_skips_verified_user(db):
    user = await _make_user(db, "verified@test.com", verified=True, age_hours=100)

    deleted = await cleanup_unverified_users(db, grace_hours=25)

    assert deleted == 0
    result = await db.execute(select(User).where(User.id == user.id))
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_cleanup_skips_admin_role(db):
    user = await _make_user(
        db, "stale_admin@test.com", verified=False, age_hours=100, role=RoleEnum.admin
    )

    deleted = await cleanup_unverified_users(db, grace_hours=25)

    assert deleted == 0
    result = await db.execute(select(User).where(User.id == user.id))
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_cleanup_cascades_tokens(db):
    user = await _make_user(db, "with_tokens@test.com", verified=False, age_hours=30)
    db.add(EmailVerificationToken(
        user_id=user.id,
        token="x" * 64,
        token_type="signup",
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    ))
    db.add(PasswordResetToken(
        user_id=user.id,
        token="y" * 64,
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    ))
    await db.commit()

    deleted = await cleanup_unverified_users(db, grace_hours=25)

    assert deleted == 1
    ev = await db.execute(
        select(EmailVerificationToken).where(EmailVerificationToken.user_id == user.id)
    )
    assert ev.scalar_one_or_none() is None
    pr = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.user_id == user.id)
    )
    assert pr.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_cleanup_frees_email_for_reregistration(client: AsyncClient, db):
    """user 註冊後 25h+ 沒驗證 → cleanup → 同 email 可再次註冊。"""
    email = "reuse@test.com"

    # 第一次註冊
    await client.post(REGISTER_URL, json={"name": "first", "email": email, "password": "abc1234567"})

    # 強制讓帳號變舊
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one()
    user.created_at = datetime.now(UTC) - timedelta(hours=30)
    await db.commit()

    # cleanup 後 email 釋出
    await cleanup_unverified_users(db, grace_hours=25)

    # 同 email 再註冊應該成功
    res = await client.post(
        REGISTER_URL, json={"name": "second", "email": email, "password": "abc1234567"}
    )
    assert res.status_code == 201
