# Code context — vuln revision


## mnemosyne/core/sync_server.py (lines 80-179)

```python
  80  
  81      def _check_auth(self) -> bool:
  82          """Check API key / JWT authentication.
  83  
  84          Returns True if request is authorized, otherwise sends 401
  85          and returns False.
  86          """
  87          if self.api_key is None and self.jwt_secret is None:
  88              return True  # No auth configured
  89  
  90          if self.api_key:
  91              auth = self.headers.get("Authorization", "")
  92              if auth.startswith("Bearer "):
  93                  token = auth[7:]
  94                  if token == self.api_key:
  95                      return True
  96              self._send_error(401, "Invalid or missing API key")
  97              return False
  98  
  99          if self.jwt_secret:
 100              auth = self.headers.get("Authorization", "")
 101              if not auth.startswith("Bearer "):
 102                  self._send_error(401, "Missing Bearer token")
 103                  return False
 104              token = auth[7:]
 105              try:
 106                  # Minimal JWT decode without dependencies
 107                  import base64 as _b64
 108                  parts = token.split(".")
 109                  if len(parts) != 3:
 110                      self._send_error(401, "Invalid JWT format")
 111                      return False
 112                  # Decode payload (part 1, 0-indexed)
 113                  payload_b64 = parts[1]
 114                  # Fix padding
 115                  pad = 4 - len(payload_b64) % 4
 116                  if pad != 4:
 117                      payload_b64 += "=" * pad
 118                  payload_bytes = _b64.urlsafe_b64decode(payload_b64)
 119                  payload = json.loads(payload_bytes.decode("utf-8"))
 120                  # Check expiry
 121                  exp = payload.get("exp", 0)
 122                  if exp and exp < datetime.now().timestamp():
 123                      self._send_error(401, "Token expired")
 124                      return False
 125                  return True
 126              except Exception as e:
 127                  self._send_error(401, f"JWT validation failed: {e}")
 128                  return False
 129  
 130          return True  # No auth configured
 131  
 132      # --- CORS preflight ---
 133      def do_OPTIONS(self) -> None:
 134          self.send_response(204)
 135          self.send_header("Access-Control-Allow-Origin", "*")
 136          self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
 137          self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
 138          self.send_header("Access-Control-Max-Age", "86400")
 139          self.end_headers()
 140  
 141      # --- POST /sync/pull ---
 142      def do_POST(self) -> None:
 143          parsed = self._parse_path(self.path)
 144          if parsed is None:
 145              self._send_error(404, f"Not found: {self.path}")
 146              return
 147  
 148          endpoint, _ = parsed
 149  
 150          if endpoint == "/sync/pull":
 151              self._handle_pull()
 152          elif endpoint == "/sync/push":
 153              self._handle_push()
 154          else:
 155              self._send_error(404, f"Not found: {self.path}")
 156  
 157      # --- GET /sync/status ---
 158      def do_GET(self) -> None:
 159          parsed = self._parse_path(self.path)
 160          if parsed is None:
 161              self._send_error(404, f"Not found: {self.path}")
 162              return
 163  
 164          endpoint, _ = parsed
 165  
 166          if endpoint == "/sync/status":
 167              self._handle_status()
 168          else:
 169              self._send_error(404, f"Not found: {self.path}")
 170  
 171      @staticmethod
 172      def _parse_path(path: str):
 173          """Parse request path, strip query string, return (path, query)."""
 174          if "?" in path:
 175              path, query = path.split("?", 1)
 176          else:
 177              query = ""
 178          # Ensure trailing slash doesn't break matching
 179          path = path.rstrip("/") or "/"
```
