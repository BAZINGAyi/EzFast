import os, json, base64
from argon2.low_level import hash_secret_raw, Type
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .base import BaseEncryption

b64e = lambda b: base64.b64encode(b).decode()
b64d = lambda s: base64.b64decode(s.encode())

class Argon2Encryption(BaseEncryption):
    def __init__(self, memory_kib=16384, time_cost=2, parallelism=1):
        self.memory_kib = memory_kib
        self.time_cost = time_cost
        self.parallelism = parallelism

    def get_kdf_name(self) -> str:
        return "argon2id"

    def encrypt(self, plaintext: bytes, password: str):
        salt = os.urandom(16)
        iv_data = os.urandom(12)
        iv_wrap = os.urandom(12)

        dek = os.urandom(32)
        kek = hash_secret_raw(
            password.encode(), salt,
            time_cost=self.time_cost,
            memory_cost=self.memory_kib,
            parallelism=self.parallelism,
            hash_len=32,
            type=Type.ID
        )

        data_ciphertext = AESGCM(dek).encrypt(iv_data, plaintext, None)
        wrapped_dek = AESGCM(kek).encrypt(iv_wrap, dek, None)

        meta = {
            "kdf": {
                "type": "argon2id",
                "salt": b64e(salt),
                "params": {
                    "memory_kib": self.memory_kib,
                    "time_cost": self.time_cost,
                    "parallelism": self.parallelism
                }
            },
            "wrap": {"iv": b64e(iv_wrap), "algo": "aes-256-gcm", "wrapped_dek": b64e(wrapped_dek)},
            "cipher": {"iv": b64e(iv_data), "algo": "aes-256-gcm"}
        }

        return {
            "data_ciphertext": b64e(data_ciphertext),
            "encryption_meta": json.dumps(meta)
        }

    def decrypt(self, data_ciphertext: str, encryption_meta: str, password: str):
        meta = json.loads(encryption_meta)
        salt = b64d(meta["kdf"]["salt"])
        params = meta["kdf"]["params"]

        kek = hash_secret_raw(
            password.encode(), salt,
            time_cost=params["time_cost"],
            memory_cost=params["memory_kib"],
            parallelism=params["parallelism"],
            hash_len=32,
            type=Type.ID
        )

        iv_data = b64d(meta["cipher"]["iv"])
        iv_wrap = b64d(meta["wrap"]["iv"])
        wrapped_dek = b64d(meta["wrap"].get("wrapped_dek", ""))
        ciphertext = b64d(data_ciphertext)

        dek = AESGCM(kek).decrypt(iv_wrap, wrapped_dek, None)
        plaintext = AESGCM(dek).decrypt(iv_data, ciphertext, None)
        return plaintext