# Code context — vuln revision


## litellm/proxy/auth/auth_utils.py (lines 133-178)

```python
 133  
 134      if model_info is None or model_info.configurable_clientside_auth_params is None:
 135          return False
 136  
 137      return _is_param_allowed(
 138          param=param,
 139          request_body_value=request_body_value,
 140          configurable_clientside_auth_params=model_info.configurable_clientside_auth_params,
 141      )
 142  
 143  
 144  def is_request_body_safe(
 145      request_body: dict, general_settings: dict, llm_router: Optional[Router], model: str
 146  ) -> bool:
 147      """
 148      Check if the request body is safe.
 149  
 150      A malicious user can set the ﻿api_base to their own domain and invoke POST /chat/completions to intercept and steal the OpenAI API key.
 151      Relevant issue: https://huntr.com/bounties/4001e1a2-7b7a-4776-a3ae-e6692ec3d997
 152      """
 153      banned_params = ["api_base", "base_url"]
 154  
 155      for param in banned_params:
 156          if (
 157              param in request_body
 158              and not check_complete_credentials(  # allow client-credentials to be passed to proxy
 159                  request_body=request_body
 160              )
 161          ):
 162              if general_settings.get("allow_client_side_credentials") is True:
 163                  return True
 164              elif (
 165                  _allow_model_level_clientside_configurable_parameters(
 166                      model=model,
 167                      param=param,
 168                      request_body_value=request_body[param],
 169                      llm_router=llm_router,
 170                  )
 171                  is True
 172              ):
 173                  return True
 174              raise ValueError(
 175                  f"Rejected Request: {param} is not allowed in request body. "
 176                  "Enable with `general_settings::allow_client_side_credentials` on proxy config.yaml. "
 177                  "Relevant Issue: https://huntr.com/bounties/4001e1a2-7b7a-4776-a3ae-e6692ec3d997",
 178              )
```

## litellm/proxy/route_llm_request.py (lines 1-43)

```python
   1  import asyncio
   2  from typing import TYPE_CHECKING, Any, Literal, Optional
   3  
   4  from fastapi import HTTPException, status
   5  
   6  import litellm
   7  
   8  if TYPE_CHECKING:
   9      from litellm.router import Router as _Router
  10  
  11      LitellmRouter = _Router
  12  else:
  13      LitellmRouter = Any
  14  
  15  
  16  def _route_user_config_request(data: dict, route_type: str):
  17      """Route a request using the user-provided router config."""
  18      router_config = data.pop("user_config")
  19  
  20      # Filter router_config to only include valid Router.__init__ arguments
  21      # This prevents TypeError when invalid parameters are stored in the database
  22      valid_args = litellm.Router.get_valid_args()
  23      filtered_config = {k: v for k, v in router_config.items() if k in valid_args}
  24  
  25      user_router = litellm.Router(**filtered_config)
  26      ret_val = getattr(user_router, f"{route_type}")(**data)
  27      user_router.discard()
  28      return ret_val
  29  
  30  
  31  def _is_a2a_agent_model(model_name: Any) -> bool:
  32      """Check if the model name is for an A2A agent (a2a/ prefix)."""
  33      return isinstance(model_name, str) and model_name.startswith("a2a/")
  34  
  35  
  36  ROUTE_ENDPOINT_MAPPING = {
  37      "acompletion": "/chat/completions",
  38      "atext_completion": "/completions",
  39      "aembedding": "/embeddings",
  40      "aimage_generation": "/image/generations",
  41      "aspeech": "/audio/speech",
  42      "atranscription": "/audio/transcriptions",
  43      "amoderation": "/moderations",
```
