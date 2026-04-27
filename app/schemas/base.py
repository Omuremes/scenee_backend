from typing import Any, Dict

from pydantic import BaseModel as PydanticBaseModel

try:
    from pydantic import ConfigDict
except ImportError:
    ConfigDict = None

_PYDANTIC_V2 = hasattr(PydanticBaseModel, "model_validate")


class BaseSchema(PydanticBaseModel):
    if _PYDANTIC_V2 and ConfigDict is not None:
        model_config = ConfigDict(from_attributes=True)
    elif not _PYDANTIC_V2:
        class Config:
            orm_mode = True

    @classmethod
    def model_validate(cls, obj: Any, *args, **kwargs):
        if isinstance(obj, cls):
            return obj
        if _PYDANTIC_V2:
            return super().model_validate(obj, *args, **kwargs)
        if isinstance(obj, dict):
            return cls.parse_obj(obj)
        return cls.from_orm(obj)

    def model_dump(self, **kwargs) -> Dict[str, Any]:
        if _PYDANTIC_V2:
            data = super().model_dump(**kwargs)
            data.pop("model_config", None)
            return data
        # В v1 вызываем оригинальный метод dict
        return super().dict(**kwargs)

    def dict(self, **kwargs) -> Dict[str, Any]:
        # В v2 перенаправляем на model_dump, в v1 вызываем оригинальный dict
        if _PYDANTIC_V2:
            return self.model_dump(**kwargs)
        return super().dict(**kwargs)
