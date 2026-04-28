from datetime import date
from uuid import UUID

from pydantic import BaseModel


class LoginResponse(BaseModel):
    id: UUID
    name: str
    role: str


class MeResponse(BaseModel):
    id: UUID
    name: str
    email: str
    pending_email: str | None
    role: str
    gender: str | None
    birthday: date | None

    model_config = {"from_attributes": True}


class VerifyEmailResponse(BaseModel):
    token_type: str


class MessageResponse(BaseModel):
    message: str
