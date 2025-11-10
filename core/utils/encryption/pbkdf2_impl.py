import os, json, base64
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from .base import BaseEncryption

b64e = lambda b: base64.b64encode(b).decode()
b64d = lambda s: base64.b64decode(s.encode())

class PBKDF2Encryption(BaseEncryption):
    def __init__(self, iterations: int = 200_000):
        self.iterations = iterations

    def get_kdf_name(self) -> str:
        return "pbkdf2"

    def encrypt(self, plaintext: bytes, password: str):
        salt = os.urandom(16)
        iv_data = os.urandom(12)
        iv_wrap = os.urandom(12)

        # derive KEK
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=self.iterations,
        )
        kek = kdf.derive(password.encode())

        # generate DEK
        dek = os.urandom(32)

        # encrypt data
        data_ciphertext = AESGCM(dek).encrypt(iv_data, plaintext, None)

        # wrap DEK
        wrapped_dek = AESGCM(kek).encrypt(iv_wrap, dek, None)

        meta = {
            "kdf": {
                "type": "pbkdf2",
                "salt": b64e(salt),
                "params": {"iterations": self.iterations, "hash": "sha256"}
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
        iv_data = b64d(meta["cipher"]["iv"])
        iv_wrap = b64d(meta["wrap"]["iv"])

        ciphertext = b64d(data_ciphertext)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=meta["kdf"]["params"]["iterations"],
        )
        kek = kdf.derive(password.encode())

        # unwrap DEK
        wrapped_dek = b64d(meta["wrap"].get("wrapped_dek", ""))
        dek = AESGCM(kek).decrypt(iv_wrap, wrapped_dek, None)

        # decrypt data
        plaintext = AESGCM(dek).decrypt(iv_data, ciphertext, None)
        return plaintext