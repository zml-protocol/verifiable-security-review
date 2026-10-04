# Code context — fixed revision


## mnemosyne/core/sync_server.py (lines 80-179)

```python
  80          except Exception as e:
  81              self._send_error(400, f"Failed to read body: {e}")
  82              return None
  83  
  84      @staticmethod
  85      def _decode_jwt_part(value: str) -> dict:
  86          """Decode one base64url-encoded JWT JSON segment."""
  87          padding = "=" * (-len(value) % 4)
  88          try:
  89              raw = base64.urlsafe_b64decode((value + padding).encode("ascii"))
  90              decoded = json.loads(raw.decode("utf-8"))
  91          except Exception as e:
  92              raise ValueError("invalid JWT encoding") from e
  93          if not isinstance(decoded, dict):
  94              raise ValueError("invalid JWT JSON")
  95          return decoded
  96  
  97      def _validate_jwt(self, token: str) -> dict:
  98          """Validate a compact HS256 JWT using the configured shared secret."""
  99          if not self.jwt_secret:
 100              raise ValueError("JWT secret is not configured")
 101  
 102          parts = token.split(".")
 103          if len(parts) != 3:
 104              raise ValueError("invalid JWT format")
 105  
 106          header = self._decode_jwt_part(parts[0])
 107          payload = self._decode_jwt_part(parts[1])
 108          algorithm = header.get("alg")
 109          if algorithm != "HS256":
 110              raise ValueError("unsupported JWT algorithm")
 111  
 112          signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
 113          expected = hmac.new(
 114              self.jwt_secret.encode("utf-8"), signing_input, hashlib.sha256
 115          ).digest()
 116          expected_sig = base64.urlsafe_b64encode(expected).decode("ascii").rstrip("=")
 117          try:
 118              valid_signature = hmac.compare_digest(parts[2], expected_sig)
 119          except TypeError as e:
 120              raise ValueError("invalid JWT signature") from e
 121          if not valid_signature:
 122              raise ValueError("invalid JWT signature")
 123  
 124          exp = payload.get("exp")
 125          if exp is not None:
 126              try:
 127                  if float(exp) < datetime.now(timezone.utc).timestamp():
 128                      raise ValueError("token expired")
 129              except (TypeError, ValueError) as e:
 130                  if isinstance(e, ValueError) and str(e) == "token expired":
 131                      raise
 132                  raise ValueError("invalid JWT exp") from e
 133          return payload
 134  
 135      def _check_auth(self) -> bool:
 136          """Check API key / JWT authentication.
 137  
 138          Returns True if request is authorized, otherwise sends 401
 139          and returns False.
 140          """
 141          if self.api_key is None and self.jwt_secret is None:
 142              return True  # No auth configured
 143  
 144          if self.api_key:
 145              auth = self.headers.get("Authorization", "")
 146              if auth.startswith("Bearer "):
 147                  token = auth[7:]
 148                  if token == self.api_key:
 149                      return True
 150              self._send_error(401, "Invalid or missing API key")
 151              return False
 152  
 153          if self.jwt_secret:
 154              auth = self.headers.get("Authorization", "")
 155              if not auth.startswith("Bearer "):
 156                  self._send_error(401, "Missing Bearer token")
 157                  return False
 158  
 159              try:
 160                  self._validate_jwt(auth[7:])
 161                  return True
 162              except ValueError as e:
 163                  self._send_error(401, f"JWT validation failed: {e}")
 164                  return False
 165  
 166          return True  # No auth configured
 167  
 168      # --- CORS preflight ---
 169      def do_OPTIONS(self) -> None:
 170          self.send_response(204)
 171          self.send_header("Access-Control-Allow-Origin", "*")
 172          self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
 173          self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
 174          self.send_header("Access-Control-Max-Age", "86400")
 175          self.end_headers()
 176  
 177      # --- POST /sync/pull ---
 178      def do_POST(self) -> None:
 179          parsed = self._parse_path(self.path)
```
