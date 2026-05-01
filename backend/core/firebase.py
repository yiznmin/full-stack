"""
Firebase Admin SDK initialization.

注入 service account 三種途徑（依優先序）：
  1. `FIREBASE_CREDENTIALS_BASE64` env var（Railway 部署用）
     base64 編碼的 service account JSON；解碼後 parse 成 dict
  2. `FIREBASE_CREDENTIALS` 字串以 `{` 開頭（任意環境直接塞 JSON）
  3. `FIREBASE_CREDENTIALS` 為檔案路徑（本地開發 ./service-account.json）

base64 是 Railway env var UI 最穩定的字串注入方式（避免 JSON 換行 / 雙引號 escape 踩雷）。
"""
import base64
import json
import logging
import os

import firebase_admin
from firebase_admin import credentials, storage

from core.config import settings

logger = logging.getLogger(__name__)

_app: firebase_admin.App | None = None


def get_firebase_app() -> firebase_admin.App:
    global _app
    if _app is not None:
        return _app

    # 優先 1：FIREBASE_CREDENTIALS_BASE64（Railway 部署）
    b64 = os.environ.get("FIREBASE_CREDENTIALS_BASE64", "").strip()
    if b64:
        # 雙重設定防呆：若 FIREBASE_CREDENTIALS 同時有值，明示 BASE64 優先
        if settings.firebase_credentials.strip():
            logger.warning(
                "FIREBASE_CREDENTIALS_BASE64 與 FIREBASE_CREDENTIALS 同時設定 — 使用 BASE64，"
                "忽略 FIREBASE_CREDENTIALS（避免設定漂移：請二選一）",
            )
        try:
            decoded = base64.b64decode(b64).decode("utf-8")
            cred = credentials.Certificate(json.loads(decoded))
        except Exception as e:
            raise RuntimeError(
                f"FIREBASE_CREDENTIALS_BASE64 解碼失敗：{type(e).__name__}: {e}"
            ) from e
    else:
        # 優先 2/3：fallback 既有路徑
        cred_value = settings.firebase_credentials.strip()
        if not cred_value:
            raise RuntimeError(
                "Firebase credentials 未設定（FIREBASE_CREDENTIALS_BASE64 "
                "或 FIREBASE_CREDENTIALS 至少設一個）"
            )
        if cred_value.startswith("{"):
            cred = credentials.Certificate(json.loads(cred_value))
        else:
            cred = credentials.Certificate(cred_value)

    _app = firebase_admin.initialize_app(
        cred,
        {"storageBucket": settings.firebase_storage_bucket},
    )
    logger.info("Firebase initialized (bucket: %s)", settings.firebase_storage_bucket)
    return _app


def get_bucket():
    get_firebase_app()
    return storage.bucket()
