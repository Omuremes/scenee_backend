from typing import Generic, TypeVar, Optional, List, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload
from app.core.database import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db

    async def get_by_id(self, id: UUID) -> Optional[ModelType]:
        result = await self.db.execute(select(self.model).where(self.model.id == id))
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        result = await self.db.execute(select(self.model).offset(skip).limit(limit))
        return result.scalars().all()

    async def create(self, obj_in: dict) -> ModelType:
        # Фильтруем поля, чтобы передать в модель только те, что в ней есть
        model_columns = self.model.__table__.columns.keys()
        data = {k: v for k, v in obj_in.items() if k in model_columns}
        
        db_obj = self.model(**data)
        self.db.add(db_obj)
        await self.db.commit()
        await self.db.refresh(db_obj)
        return db_obj

    async def update(self, id: UUID, obj_in: dict) -> Optional[ModelType]:
        # Фильтруем поля для обновления
        model_columns = self.model.__table__.columns.keys()
        data = {k: v for k, v in obj_in.items() if k in model_columns}
        
        result = await self.db.execute(
            update(self.model).where(self.model.id == id).values(**data).returning(self.model)
        )
        await self.db.commit()
        return result.scalar_one_or_none()

    async def delete(self, id: UUID) -> bool:
        result = await self.db.execute(delete(self.model).where(self.model.id == id))
        await self.db.commit()
        return result.rowcount > 0

    async def exists(self, id: UUID) -> bool:
        result = await self.db.execute(select(self.model.id).where(self.model.id == id))
        return result.scalar_one_or_none() is not None