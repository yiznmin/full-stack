"""一次性：設定 Firebase Storage bucket 的 CORS，允許 localhost / Vercel 直傳。

執行：
    cd backend && venv/Scripts/python scripts/set_firebase_cors.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import core._windows_compat  # noqa: F401, E402
from core.firebase import get_bucket  # noqa: E402

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    # 上線後在這裡加 Vercel 網域，例如：
    # "https://yiimui-admin.vercel.app",
    # "https://yiimui-store.vercel.app",
]

CORS_RULES = [
    {
        "origin": ALLOWED_ORIGINS,
        "method": ["PUT", "GET", "HEAD", "OPTIONS"],
        "responseHeader": ["Content-Type"],
        "maxAgeSeconds": 3600,
    }
]


def main():
    bucket = get_bucket()
    print(f"Bucket: {bucket.name}")
    print(f"Current CORS: {bucket.cors}")
    bucket.cors = CORS_RULES
    bucket.patch()
    print(f"New CORS: {bucket.cors}")
    print("OK")


if __name__ == "__main__":
    main()
