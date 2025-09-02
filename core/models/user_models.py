from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Boolean, ForeignKey, BigInteger, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import generate_password_hash, check_password_hash

from .base_models import Base, CommonModelMixin


class User(Base, CommonModelMixin):
    """系统用户表"""
    __tablename__ = "sys_user"

    username: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True, comment="用户名"
    )
    email: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True, comment="邮箱地址"
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="密码哈希值"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, comment="是否激活"
    )
    phone_number: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="手机号码"
    )
    last_login_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True, comment="最后登录时间"
    )
    locale: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, default="zh-CN", comment="语言区域"
    )
    role_id: Mapped[int] = mapped_column(
        ForeignKey("sys_role.id"), nullable=False, comment="角色ID"
    )

    @property
    def password(self) -> str:
        """密码属性的 getter，返回哈希值"""
        return self.password_hash

    @password.setter
    def password(self, password: str) -> None:
        """密码属性的 setter，自动进行哈希"""
        self.set_password(password)

    def set_password(self, password: str) -> None:
        """生成密码哈希值并设置"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """验证密码是否正确"""
        return check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_active': self.is_active,
            'phone_number': self.phone_number,
            'locale': self.locale,
            'role_id': self.role_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"


class Role(Base, CommonModelMixin):
    """系统角色表"""
    __tablename__ = "sys_role"

    name: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, comment="角色名称"
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="角色描述"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, comment="是否激活"
    )

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, name='{self.name}')>"


class Module(Base, CommonModelMixin):
    """系统模块表"""
    __tablename__ = "sys_module"

    name: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, comment="模块名称"
    )
    url: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="模块URL"
    )
    icon: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="模块图标"
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sys_module.id"), nullable=True, comment="父模块ID"
    )
    path: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="模块路径"
    )

    def __repr__(self) -> str:
        return f"<Module(id={self.id}, name='{self.name}')>"


class Permission(Base, CommonModelMixin):
    """系统权限表"""
    __tablename__ = "sys_permission"

    name: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, comment="权限名称"
    )

    permission_bit = mapped_column(
        BigInteger, nullable=False, comment="权限位"
    )

    description: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True, comment="权限描述"
    )

    def __repr__(self) -> str:
        return f"<Permission(id={self.id}, name='{self.name}')>"


class ModulePermission(Base):
    """模块权限关联表 - 定义模块可拥有的权限模板"""
    __tablename__ = "sys_module_permission"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    module_id: Mapped[int] = mapped_column(
        ForeignKey("sys_module.id"), nullable=False, comment="模块ID"
    )
    permission_id: Mapped[int] = mapped_column(
        ForeignKey("sys_permission.id"), nullable=False, comment="权限ID"
    )

    def __repr__(self) -> str:
        return f"<ModulePermission(module_id={self.module_id}, permission_id={self.permission_id})>"


class RoleModulePermission(Base):
    """角色模块权限表 - 角色对模块的实际权限"""
    __tablename__ = "sys_role_module_permission"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    role_id: Mapped[int] = mapped_column(
        ForeignKey("sys_role.id"), nullable=False, comment="角色ID"
    )
    module_id: Mapped[int] = mapped_column(
        ForeignKey("sys_module.id"), nullable=False, comment="模块ID"
    )
    permissions: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, default=0, comment="权限位掩码"
    )

    def __repr__(self) -> str:
        return f"<RoleModulePermission(role_id={self.role_id}, module_id={self.module_id})>"

    def set_permission(self, permission_id: int) -> None:
        """设置指定的权限"""
        if permission_id is not None:
            if self.permissions is None:
                self.permissions = 0
            self.permissions |= permission_id

    def remove_permission(self, permission_id: int) -> None:
        """移除指定的权限"""
        if permission_id and self.permissions:
            self.permissions &= ~permission_id

    def has_permission(self, permission_id: int) -> bool:
        """检查是否具有指定的权限"""
        if permission_id and self.permissions:
            return (self.permissions & permission_id) == permission_id
        return False


class OperationLog(Base, CommonModelMixin):
    """系统操作日志表"""
    __tablename__ = "sys_operation_log"
    
    user_id: Mapped[int] = mapped_column(
        ForeignKey("sys_user.id"), nullable=False, comment="操作用户ID"
    )
    module_id: Mapped[int] = mapped_column(
        ForeignKey("sys_module.id"), nullable=False, comment="操作模块ID"
    )

    def __repr__(self) -> str:
        return f"<OperationLog(user_id={self.user_id}, module_id={self.module_id})>"