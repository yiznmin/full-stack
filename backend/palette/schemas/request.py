from uuid import UUID

from pydantic import BaseModel


class UpdateMappingRequest(BaseModel):
    physical_color_id: UUID
