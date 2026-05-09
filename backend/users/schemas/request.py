import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, EmailStr, field_validator, model_validator


def _validate_password(v: str) -> str:
    if len(v) < 10:
        raise ValueError("密碼至少需要 10 個字元")
    if not re.search(r"[A-Za-z]", v):
        raise ValueError("密碼需包含英文字母")
    if not re.search(r"\d", v):
        raise ValueError("密碼需包含數字")
    return v


class UpdateProfileRequest(BaseModel):
    name: str | None = None
    gender: Literal["female", "male", "other"] | None = None
    birthday: date | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if v is not None and len(v) < 4:
            raise ValueError("名稱至少需要 4 個字元")
        return v


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return _validate_password(v)


class RequestEmailChangeRequest(BaseModel):
    new_email: EmailStr


class ShippingProfileRequest(BaseModel):
    """收件資料 request — 對應 docs/integration_specs/ecpay_cvs_map.md §11.3 用戶輸入欄位限制。

    欄位長度限制原則：
    - recipient_name 30：合理姓名上限
    - city / district 20：台灣縣市行政區最長約 6 字，留 20 容錯（中文符號、英文）
    - address_detail 200：街道路名 + 巷弄號樓 + 補充說明合理上限
    - store_id 9：ECpay 規定 (CVSStoreID 最多 9 字元)
    - store_name 20：ECpay 文件 10、留 20 容錯（門市可能有副名稱）
    """
    shipping_type: Literal["home", "seven_eleven", "family_mart"]
    recipient_name: str
    phone: str
    email: EmailStr | None = None
    city: str | None = None
    district: str | None = None
    address_detail: str | None = None
    store_id: str | None = None
    store_name: str | None = None
    is_default: bool = False

    @field_validator("recipient_name")
    @classmethod
    def validate_recipient_name(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("收件人姓名不可空白")
        if len(v) > 30:
            raise ValueError("收件人姓名不可超過 30 字")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        if not re.fullmatch(r"09\d{8}", v):
            raise ValueError("電話格式錯誤，需為台灣手機號碼（09xxxxxxxx）")
        return v

    @field_validator("city")
    @classmethod
    def validate_city(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if len(v) > 20:
            raise ValueError("縣市名稱過長")
        return v

    @field_validator("district")
    @classmethod
    def validate_district(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if len(v) > 20:
            raise ValueError("行政區名稱過長")
        return v

    @field_validator("address_detail")
    @classmethod
    def validate_address_detail(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if len(v) > 200:
            raise ValueError("地址不可超過 200 字")
        return v

    @field_validator("store_id")
    @classmethod
    def validate_store_id(cls, v: str | None) -> str | None:
        # ECpay CVSStoreID 規定最多 9 字元、英數
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if len(v) > 9:
            raise ValueError("門市代碼不可超過 9 字元")
        if not re.fullmatch(r"[A-Za-z0-9]+", v):
            raise ValueError("門市代碼僅能為英數字")
        return v

    @field_validator("store_name")
    @classmethod
    def validate_store_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if len(v) > 20:
            raise ValueError("門市名稱過長")
        return v

    @model_validator(mode="after")
    def validate_fields_by_type(self) -> "ShippingProfileRequest":
        if self.shipping_type == "home":
            missing = [f for f in ("city", "district", "address_detail") if not getattr(self, f)]
            if missing:
                raise ValueError(f"宅配到府必填：{', '.join(missing)}")
        else:
            missing = [f for f in ("store_id", "store_name") if not getattr(self, f)]
            if missing:
                raise ValueError(f"超商取件必填：{', '.join(missing)}")
        return self
