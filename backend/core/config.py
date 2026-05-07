from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    test_database_url: str = ""

    @field_validator("database_url", "test_database_url")
    @classmethod
    def _normalize_async_driver(cls, v: str) -> str:
        """Railway PostgreSQL plugin 注入 `postgresql://...`，但 backend 用 SQLAlchemy
        async + asyncpg driver — URL scheme 必須是 `postgresql+asyncpg://...`。
        本地 .env 已寫對；雲端 reference 自動補 +asyncpg。
        """
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_days_customer: int = 7
    jwt_expire_hours_admin: int = 8

    resend_api_key: str = ""
    resend_from_email: str = "onboarding@resend.dev"
    frontend_url: str = "http://localhost:5173"
    admin_url: str = "http://localhost:5174"

    firebase_credentials: str = ""
    firebase_storage_bucket: str = ""

    redis_url: str = "redis://localhost:6379/0"

    # SAM 模型檔（vit_b ~375MB）；本地預設指向 paint-by-number/models/sam_vit_b.pth
    # 部署環境由 Dockerfile RUN curl 下載到 /app/models/ 並設此 env var
    sam_model_path: str | None = None

    # ── ECpay 物流（CVS Map / 超商選店）──────────────────────────────────
    # 物流產品的 MerchantID / HashKey / HashIV（與電子發票是不同帳號）
    ecpay_merchant_id: str = ""
    ecpay_hash_key: str = ""
    ecpay_hash_iv: str = ""
    # 'stage' = 沙箱（logistics-stage.ecpay.com.tw）
    # 'production' = 正式（logistics.ecpay.com.tw）
    ecpay_env: str = "stage"
    # ServerReplyURL：ECpay 把選店結果 POST 回我們的 callback URL（必須可被外網存取）
    # 預設留空 → service 由 request.base_url 自動推導
    ecpay_server_reply_url: str = ""

    @field_validator(
        "ecpay_merchant_id", "ecpay_hash_key", "ecpay_hash_iv",
        "ecpay_env", "ecpay_server_reply_url",
    )
    @classmethod
    def _strip_ecpay(cls, v: str) -> str:
        """環境變數複製貼上常帶換行 / 前後空白；strip 掉避免簽章對不起來。"""
        return v.strip() if v else v

    class Config:
        env_file = ".env"


settings = Settings()
