from datetime import datetime, timezone
from typing import Any, Dict
from sqlalchemy.inspection import inspect
from sqlalchemy import Integer, Column, DateTime, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
import pytz

class Base(DeclarativeBase):
    __abstract__ = True  # 抽象基类，不会生成表

china_tz = pytz.timezone('Asia/Shanghai')

class CommonModelMixin:
    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(china_tz),
        onupdate=lambda: datetime.now(china_tz)
    )

    description: Mapped[str] = mapped_column(Text, nullable=True)

    def to_dict(self) -> Dict[str, Any]:
        """把 ORM 对象转换成字典"""
        return {
            c.key: getattr(self, c.key)
            for c in inspect(self).mapper.column_attrs
        }