from typing import Any

from pydantic import BaseModel as PydanticBaseModel

try:
    from pydantic import ConfigDict
except ImportError:
    ConfigDict = None

_PYDANTIC_V2 = hasattr(PydanticBaseModel, "model_validate")


class BaseSchema(PydanticBaseModel):
    if ConfigDict is not None:
        model_config = ConfigDict(from_attributes=True)

    @classmethod
    def model_validate(cls, obj: Any):
        if isinstance(obj, cls):
            return obj
        if _PYDANTIC_V2:
            return PydanticBaseModel.model_validate.__func__(cls, obj, from_attributes=True)
        if isinstance(obj, dict):
            return cls.parse_obj(obj)
        return cls.from_orm(obj)

    def model_dump(self, **kwargs):
        if _PYDANTIC_V2:
            return PydanticBaseModel.model_dump(self, **kwargs)
        return self.dict(**kwargs)

    if not _PYDANTIC_V2:
        class Config:
            orm_mode = True
