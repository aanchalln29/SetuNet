"""Ed25519 Digital Signature and Integrity Verification.

Implements digital signatures for SETU-NET alerts as specified in Slides 4, 6, 7 & 10.
Includes an RFC 8032-compatible pure-Python Ed25519 engine (with zero external dependencies)
and seamlessly uses the native `cryptography` library if installed for maximum hardware speed.
"""

from __future__ import annotations

import hashlib
import os
import secrets
from typing import Tuple

# Try native cryptography library first; fallback to pure-Python engine
_HAS_NATIVE_ED25519 = False
try:
    from cryptography.hazmat.primitives.asymmetric import ed25519
    _HAS_NATIVE_ED25519 = True
except ImportError:
    _HAS_NATIVE_ED25519 = False


# ==============================================================================
# Pure-Python Ed25519 (RFC 8032 / Edwards-curve Digital Signature Algorithm)
# ==============================================================================
_B = 256
_Q = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493

def _inv(x: int) -> int:
    return pow(x, _Q - 2, _Q)

_D = -121665 * _inv(121666) % _Q
_I = pow(2, (_Q - 1) // 4, _Q)

def _xrecover(y: int) -> int:
    xx = (y * y - 1) * _inv(_D * y * y + 1)
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q != 0:
        x = (x * _I) % _Q
    if x % 2 != 0:
        x = _Q - x
    return x

_BY = 4 * _inv(5) % _Q
_BX = _xrecover(_BY)
_BP = (_BX, _BY)

def _edwards_add(p: Tuple[int, int], q: Tuple[int, int]) -> Tuple[int, int]:
    x1, y1 = p
    x2, y2 = q
    x3 = (x1 * y2 + x2 * y1) * _inv(1 + _D * x1 * x2 * y1 * y2) % _Q
    y3 = (y1 * y2 + x1 * x2) * _inv(1 - _D * x1 * x2 * y1 * y2) % _Q
    return (x3, y3)

def _scalar_mult(p: Tuple[int, int], e: int) -> Tuple[int, int]:
    if e == 0:
        return (0, 1)
    q = _scalar_mult(p, e // 2)
    q = _edwards_add(q, q)
    if e & 1:
        q = _edwards_add(q, p)
    return q

def _encodeint(y: int) -> bytes:
    bits = [(y >> i) & 1 for i in range(_B)]
    return bytes(sum([bits[i * 8 + j] << j for j in range(8)]) for i in range(_B // 8))

def _encodepoint(p: Tuple[int, int]) -> bytes:
    x, y = p
    bits = [(y >> i) & 1 for i in range(_B - 1)] + [x & 1]
    return bytes(sum([bits[i * 8 + j] << j for j in range(8)]) for i in range(_B // 8))

def _bit(h: bytes, i: int) -> int:
    return (h[i // 8] >> (i % 8)) & 1

def _decodeint(b: bytes) -> int:
    return sum(2**i * _bit(b, i) for i in range(0, _B))

def _decodepoint(b: bytes) -> Tuple[int, int] | None:
    y = sum(2**i * _bit(b, i) for i in range(0, _B - 1))
    x = _xrecover(y)
    if x & 1 != _bit(b, _B - 1):
        x = _Q - x
    p = (x, y)
    # Verify on curve
    if (-x * x + y * y - 1 - _D * x * x * y * y) % _Q != 0:
        return None
    return p

def _h(m: bytes) -> bytes:
    return hashlib.sha512(m).digest()

def _pure_public_key(secret_seed: bytes) -> bytes:
    h = _h(secret_seed)
    a = 2**(_B - 2) + sum(2**i * _bit(h, i) for i in range(3, _B - 2))
    a_point = _scalar_mult(_BP, a)
    return _encodepoint(a_point)

def _pure_sign(secret_seed: bytes, message: bytes) -> bytes:
    h = _h(secret_seed)
    a = 2**(_B - 2) + sum(2**i * _bit(h, i) for i in range(3, _B - 2))
    pub = _pure_public_key(secret_seed)
    r_bytes = _h(h[32:] + message)
    r = sum(2**i * _bit(r_bytes, i) for i in range(0, 2 * _B))
    r_point = _scalar_mult(_BP, r)
    k_bytes = _h(_encodepoint(r_point) + pub + message)
    k = sum(2**i * _bit(k_bytes, i) for i in range(0, 2 * _B))
    s = (r + k * a) % _L
    return _encodepoint(r_point) + _encodeint(s)

def _pure_verify(public_key_bytes: bytes, message: bytes, signature_bytes: bytes) -> bool:
    if len(signature_bytes) != 64 or len(public_key_bytes) != 32:
        return False
    try:
        r_point = _decodepoint(signature_bytes[:32])
        a_point = _decodepoint(public_key_bytes)
        if r_point is None or a_point is None:
            return False
        s = _decodeint(signature_bytes[32:])
        if s >= _L:
            return False
        k_bytes = _h(signature_bytes[:32] + public_key_bytes + message)
        k = sum(2**i * _bit(k_bytes, i) for i in range(0, 2 * _B))
        sb = _scalar_mult(_BP, s)
        ra = _edwards_add(r_point, _scalar_mult(a_point, k))
        return sb == ra
    except Exception:
        return False


# ==============================================================================
# Public SETU-NET Cryptographic Interface
# ==============================================================================
class KeyPair:
    """Represents an Ed25519 signing keypair for an Android emergency node."""

    def __init__(self, private_bytes: bytes, public_bytes: bytes):
        self.private_bytes = private_bytes
        self.public_bytes = public_bytes

    @property
    def public_hex(self) -> str:
        return self.public_bytes.hex()

    @property
    def private_hex(self) -> str:
        return self.private_bytes.hex()


def generate_keypair(seed: bytes | None = None) -> KeyPair:
    """Generate a 32-byte Ed25519 keypair."""
    secret = seed if seed is not None else secrets.token_bytes(32)
    if len(secret) != 32:
        secret = hashlib.sha256(secret).digest()

    if _HAS_NATIVE_ED25519:
        try:
            priv = ed25519.Ed25519PrivateKey.from_private_bytes(secret)
            pub = priv.public_key().public_bytes_raw()
            return KeyPair(secret, pub)
        except Exception:
            pass

    pub = _pure_public_key(secret)
    return KeyPair(secret, pub)


def sign_message(keypair: KeyPair, message_bytes: bytes) -> str:
    """Sign canonical alert message bytes with the private key. Returns hex signature."""
    if _HAS_NATIVE_ED25519:
        try:
            priv = ed25519.Ed25519PrivateKey.from_private_bytes(keypair.private_bytes)
            sig = priv.sign(message_bytes)
            return sig.hex()
        except Exception:
            pass

    sig = _pure_sign(keypair.private_bytes, message_bytes)
    return sig.hex()


def verify_signature(public_key_hex: str, message_bytes: bytes, signature_hex: str) -> bool:
    """Verify an Ed25519 signature over canonical alert bytes."""
    if not public_key_hex or not signature_hex:
        return False

    try:
        pub_bytes = bytes.fromhex(public_key_hex)
        sig_bytes = bytes.fromhex(signature_hex)
    except (ValueError, TypeError):
        return False

    if _HAS_NATIVE_ED25519:
        try:
            pub = ed25519.Ed25519PublicKey.from_public_bytes(pub_bytes)
            pub.verify(sig_bytes, message_bytes)
            return True
        except Exception:
            pass

    return _pure_verify(pub_bytes, message_bytes, sig_bytes)
