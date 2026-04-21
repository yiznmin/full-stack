"""
Firebase Admin SDK initialization.

FIREBASE_CREDENTIALS 支援兩種格式：
  - 檔案路徑（本地開發）：./service-account.json
  - JSON 字串（Railway 部署）：{"type":"service_account","project_id":...}
"""
import json
import logging

import firebase_admin
from firebase_admin import credentials, storage

from core.config import settings

logger = logging.getLogger(__name__)

_app: firebase_admin.App | None = None


def get_firebase_app() -> firebase_admin.App:
    global _app
    if _app is not None:
        return _app

    cred_value = settings.firebase_credentials.strip()
    if not cred_value:
        raise RuntimeError("FIREBASE_CREDENTIALS 未設定")

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
