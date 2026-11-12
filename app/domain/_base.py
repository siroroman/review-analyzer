from pydantic import BaseModel, ConfigDict


class DomainModel(BaseModel):
    """Base of every domain type: immutable, no unknown fields, no silent type coercion."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)
