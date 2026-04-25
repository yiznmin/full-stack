from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class UpdateNotificationStatusRequest(BaseModel):
    status: Literal["in_progress", "completed"]


class BulkCompleteRequest(BaseModel):
    ids: list[UUID]
