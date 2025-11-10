from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict

class BaseEncryption(ABC):
    """
    抽象基类：定义统一接口和返回结构
    """

    @abstractmethod
    def encrypt(self, plaintext: bytes, password: str) -> Dict[str, str]:
        """
        加密明文，返回统一格式：
        {
            "data_ciphertext": <base64>,
            "encryption_meta": <json string>
        }
        """
        pass

    @abstractmethod
    def decrypt(self, data_ciphertext: str, encryption_meta: str, password: str) -> bytes:
        """
        解密：根据 encryption_meta 解析算法和参数。
        返回明文字节。
        """
        pass

    @abstractmethod
    def get_kdf_name(self) -> str:
        """
        返回算法标识符，如 "pbkdf2" 或 "argon2id"
        """
        pass
