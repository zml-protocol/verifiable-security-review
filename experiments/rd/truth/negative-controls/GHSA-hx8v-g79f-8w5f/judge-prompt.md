# RD negative-control adjudication — GHSA-hx8v-g79f-8w5f

You are one of two independent adjudicators. Work only from this message; do not use outside project
knowledge. Return only the YAML object requested at the end.

For each candidate and each canonical revision, assess this package-wide existential claim:

> In the Python LiteLLM Proxy package, attacker-controlled input may lead to the candidate CWE.

Use exactly one label:

- SUPPORTED: the evidence establishes at least one instance of the claim in that revision.
- NOT_SUPPORTED: the evidence establishes that the claim is false in that revision.
- INDETERMINATE: neither conclusion is justified by the evidence.

Judge all six cells independently. A text search match does not by itself establish a CWE. No search
match is sufficient for NOT_SUPPORTED only when the complete inventory and package surface make the
missing primitive dispositive; otherwise use INDETERMINATE. Do not infer a label from the candidate
order or from the fact that this is a negative-control task.

Candidates, in frozen order:

1. candidate-01: CWE-502 Deserialization of Untrusted Data
2. candidate-02: CWE-601 Open Redirect
3. candidate-03: CWE-611 XML External Entity

---

# Factual evidence

## Revision and package scope

- Package under adjudication: the Python product-source subtree litellm/proxy/ (LiteLLM Proxy).
- vuln: 93faf321df159b1ef65a98cc29a70958a96d184a
- fixed: 47214be317f45a2d2ac08258362e0481411eb427
- The already-observed real behavior is that a request body can put api_base inside user_config and
  steer an upstream request. The security-fix hunk adds user_config to the request-body guard's
  banned_params list.
- The candidate-relevant excerpts and all frozen-regex outputs below are unchanged between the two
  revisions.

The real security-fix hunk is:

```diff
-    banned_params = ["api_base", "base_url"]
+    banned_params = ["api_base", "base_url", "user_config"]
```

## Complete product-source inventory

The inventory rule is tracked .py files under litellm/proxy/, excluding path components test, tests,
.venv, venv, build, and dist. The sorted inventories are byte-identical in vuln and fixed: 394 files,
with list SHA-256 d293f98ff1e952f9ce8b7193a6bfd971c58698f492bfa35c8c0ecc9080b0b2f6.

```text
litellm/proxy/__init__.py
litellm/proxy/_experimental/mcp_server/auth/litellm_auth_handler.py
litellm/proxy/_experimental/mcp_server/auth/user_api_key_auth_mcp.py
litellm/proxy/_experimental/mcp_server/byok_oauth_endpoints.py
litellm/proxy/_experimental/mcp_server/cost_calculator.py
litellm/proxy/_experimental/mcp_server/db.py
litellm/proxy/_experimental/mcp_server/discoverable_endpoints.py
litellm/proxy/_experimental/mcp_server/guardrail_translation/__init__.py
litellm/proxy/_experimental/mcp_server/guardrail_translation/handler.py
litellm/proxy/_experimental/mcp_server/mcp_context.py
litellm/proxy/_experimental/mcp_server/mcp_debug.py
litellm/proxy/_experimental/mcp_server/mcp_server_manager.py
litellm/proxy/_experimental/mcp_server/oauth2_token_cache.py
litellm/proxy/_experimental/mcp_server/openapi_to_mcp_generator.py
litellm/proxy/_experimental/mcp_server/rest_endpoints.py
litellm/proxy/_experimental/mcp_server/semantic_tool_filter.py
litellm/proxy/_experimental/mcp_server/server.py
litellm/proxy/_experimental/mcp_server/sse_transport.py
litellm/proxy/_experimental/mcp_server/tool_registry.py
litellm/proxy/_experimental/mcp_server/toolset_db.py
litellm/proxy/_experimental/mcp_server/ui_session_utils.py
litellm/proxy/_experimental/mcp_server/utils.py
litellm/proxy/_experimental/post_call_rules.py
litellm/proxy/_logging.py
litellm/proxy/_types.py
litellm/proxy/agent_endpoints/a2a_endpoints.py
litellm/proxy/agent_endpoints/a2a_routing.py
litellm/proxy/agent_endpoints/agent_registry.py
litellm/proxy/agent_endpoints/auth/__init__.py
litellm/proxy/agent_endpoints/auth/agent_permission_handler.py
litellm/proxy/agent_endpoints/endpoints.py
litellm/proxy/agent_endpoints/model_list_helpers.py
litellm/proxy/agent_endpoints/utils.py
litellm/proxy/analytics_endpoints/analytics_endpoints.py
litellm/proxy/anthropic_endpoints/claude_code_endpoints/__init__.py
litellm/proxy/anthropic_endpoints/claude_code_endpoints/claude_code_marketplace.py
litellm/proxy/anthropic_endpoints/endpoints.py
litellm/proxy/anthropic_endpoints/skills_endpoints.py
litellm/proxy/auth/auth_checks.py
litellm/proxy/auth/auth_checks_organization.py
litellm/proxy/auth/auth_exception_handler.py
litellm/proxy/auth/auth_utils.py
litellm/proxy/auth/handle_jwt.py
litellm/proxy/auth/ip_address_utils.py
litellm/proxy/auth/litellm_license.py
litellm/proxy/auth/login_utils.py
litellm/proxy/auth/model_checks.py
litellm/proxy/auth/oauth2_check.py
litellm/proxy/auth/oauth2_proxy_hook.py
litellm/proxy/auth/rds_iam_token.py
litellm/proxy/auth/route_checks.py
litellm/proxy/auth/user_api_key_auth.py
litellm/proxy/batches_endpoints/endpoints.py
litellm/proxy/caching_routes.py
litellm/proxy/client/__init__.py
litellm/proxy/client/chat.py
litellm/proxy/client/cli/__init__.py
litellm/proxy/client/cli/commands/__init__.py
litellm/proxy/client/cli/commands/auth.py
litellm/proxy/client/cli/commands/chat.py
litellm/proxy/client/cli/commands/credentials.py
litellm/proxy/client/cli/commands/http.py
litellm/proxy/client/cli/commands/keys.py
litellm/proxy/client/cli/commands/models.py
litellm/proxy/client/cli/commands/teams.py
litellm/proxy/client/cli/commands/users.py
litellm/proxy/client/cli/interface.py
litellm/proxy/client/cli/main.py
litellm/proxy/client/client.py
litellm/proxy/client/credentials.py
litellm/proxy/client/exceptions.py
litellm/proxy/client/health.py
litellm/proxy/client/http_client.py
litellm/proxy/client/keys.py
litellm/proxy/client/model_groups.py
litellm/proxy/client/models.py
litellm/proxy/client/teams.py
litellm/proxy/client/users.py
litellm/proxy/common_request_processing.py
litellm/proxy/common_utils/admin_ui_utils.py
litellm/proxy/common_utils/banner.py
litellm/proxy/common_utils/cache_coordinator.py
litellm/proxy/common_utils/callback_utils.py
litellm/proxy/common_utils/custom_openapi_spec.py
litellm/proxy/common_utils/debug_utils.py
litellm/proxy/common_utils/encrypt_decrypt_utils.py
litellm/proxy/common_utils/get_routes.py
litellm/proxy/common_utils/html_forms/cli_sso_success.py
litellm/proxy/common_utils/html_forms/jwt_display_template.py
litellm/proxy/common_utils/html_forms/ui_login.py
litellm/proxy/common_utils/http_parsing_utils.py
litellm/proxy/common_utils/key_rotation_manager.py
litellm/proxy/common_utils/load_config_utils.py
litellm/proxy/common_utils/openai_endpoint_utils.py
litellm/proxy/common_utils/openapi_schema_compat.py
litellm/proxy/common_utils/performance_utils.py
litellm/proxy/common_utils/proxy_state.py
litellm/proxy/common_utils/rbac_utils.py
litellm/proxy/common_utils/realtime_utils.py
litellm/proxy/common_utils/reset_budget_job.py
litellm/proxy/common_utils/swagger_utils.py
litellm/proxy/common_utils/timezone_utils.py
litellm/proxy/compliance_checks.py
litellm/proxy/config_management_endpoints/pass_through_endpoints.py
litellm/proxy/container_endpoints/__init__.py
litellm/proxy/container_endpoints/endpoints.py
litellm/proxy/container_endpoints/handler_factory.py
litellm/proxy/credential_endpoints/endpoints.py
litellm/proxy/custom_auth_auto.py
litellm/proxy/custom_hooks/custom_ui_sso_hook.py
litellm/proxy/custom_prompt_management.py
litellm/proxy/custom_sso.py
litellm/proxy/custom_validate.py
litellm/proxy/db/base_client.py
litellm/proxy/db/check_migration.py
litellm/proxy/db/create_views.py
litellm/proxy/db/db_spend_update_writer.py
litellm/proxy/db/db_transaction_queue/base_update_queue.py
litellm/proxy/db/db_transaction_queue/daily_spend_update_queue.py
litellm/proxy/db/db_transaction_queue/pod_lock_manager.py
litellm/proxy/db/db_transaction_queue/redis_update_buffer.py
litellm/proxy/db/db_transaction_queue/spend_log_cleanup.py
litellm/proxy/db/db_transaction_queue/spend_update_queue.py
litellm/proxy/db/db_transaction_queue/tool_discovery_queue.py
litellm/proxy/db/dynamo_db.py
litellm/proxy/db/exception_handler.py
litellm/proxy/db/log_db_metrics.py
litellm/proxy/db/prisma_client.py
litellm/proxy/db/spend_log_tool_index.py
litellm/proxy/db/tool_registry_writer.py
litellm/proxy/dd_span_tagger.py
litellm/proxy/discovery_endpoints/__init__.py
litellm/proxy/discovery_endpoints/ui_discovery_endpoints.py
litellm/proxy/example_config_yaml/custom_auth.py
litellm/proxy/example_config_yaml/custom_auth_basic.py
litellm/proxy/example_config_yaml/custom_callbacks.py
litellm/proxy/example_config_yaml/custom_callbacks1.py
litellm/proxy/example_config_yaml/custom_guardrail.py
litellm/proxy/example_config_yaml/custom_handler.py
litellm/proxy/example_config_yaml/pipeline_test_guardrails.py
litellm/proxy/fine_tuning_endpoints/endpoints.py
litellm/proxy/google_endpoints/endpoints.py
litellm/proxy/guardrails/guardrail_endpoints.py
litellm/proxy/guardrails/guardrail_helpers.py
litellm/proxy/guardrails/guardrail_hooks/aim/__init__.py
litellm/proxy/guardrails/guardrail_hooks/aim/aim.py
litellm/proxy/guardrails/guardrail_hooks/akto/__init__.py
litellm/proxy/guardrails/guardrail_hooks/akto/akto.py
litellm/proxy/guardrails/guardrail_hooks/aporia_ai/__init__.py
litellm/proxy/guardrails/guardrail_hooks/aporia_ai/aporia_ai.py
litellm/proxy/guardrails/guardrail_hooks/azure/__init__.py
litellm/proxy/guardrails/guardrail_hooks/azure/base.py
litellm/proxy/guardrails/guardrail_hooks/azure/prompt_shield.py
litellm/proxy/guardrails/guardrail_hooks/azure/text_moderation.py
litellm/proxy/guardrails/guardrail_hooks/bedrock_guardrails.py
litellm/proxy/guardrails/guardrail_hooks/block_code_execution/__init__.py
litellm/proxy/guardrails/guardrail_hooks/block_code_execution/block_code_execution.py
litellm/proxy/guardrails/guardrail_hooks/crowdstrike_aidr/__init__.py
litellm/proxy/guardrails/guardrail_hooks/crowdstrike_aidr/crowdstrike_aidr.py
litellm/proxy/guardrails/guardrail_hooks/custom_code/__init__.py
litellm/proxy/guardrails/guardrail_hooks/custom_code/custom_code_guardrail.py
litellm/proxy/guardrails/guardrail_hooks/custom_code/primitives.py
litellm/proxy/guardrails/guardrail_hooks/custom_code/response_rejection_code.py
litellm/proxy/guardrails/guardrail_hooks/custom_code/sandbox.py
litellm/proxy/guardrails/guardrail_hooks/custom_guardrail.py
litellm/proxy/guardrails/guardrail_hooks/dynamoai/__init__.py
litellm/proxy/guardrails/guardrail_hooks/dynamoai/dynamoai.py
litellm/proxy/guardrails/guardrail_hooks/enkryptai/__init__.py
litellm/proxy/guardrails/guardrail_hooks/enkryptai/enkryptai.py
litellm/proxy/guardrails/guardrail_hooks/generic_guardrail_api/__init__.py
litellm/proxy/guardrails/guardrail_hooks/generic_guardrail_api/generic_guardrail_api.py
litellm/proxy/guardrails/guardrail_hooks/grayswan/__init__.py
litellm/proxy/guardrails/guardrail_hooks/grayswan/grayswan.py
litellm/proxy/guardrails/guardrail_hooks/guardrails_ai/__init__.py
litellm/proxy/guardrails/guardrail_hooks/guardrails_ai/guardrails_ai.py
litellm/proxy/guardrails/guardrail_hooks/hiddenlayer/__init__.py
litellm/proxy/guardrails/guardrail_hooks/hiddenlayer/hiddenlayer.py
litellm/proxy/guardrails/guardrail_hooks/ibm_guardrails/__init__.py
litellm/proxy/guardrails/guardrail_hooks/ibm_guardrails/ibm_detector.py
litellm/proxy/guardrails/guardrail_hooks/javelin/__init__.py
litellm/proxy/guardrails/guardrail_hooks/javelin/javelin.py
litellm/proxy/guardrails/guardrail_hooks/lakera_ai.py
litellm/proxy/guardrails/guardrail_hooks/lakera_ai_v2.py
litellm/proxy/guardrails/guardrail_hooks/lasso/__init__.py
litellm/proxy/guardrails/guardrail_hooks/lasso/lasso.py
litellm/proxy/guardrails/guardrail_hooks/litellm_content_filter/__init__.py
litellm/proxy/guardrails/guardrail_hooks/litellm_content_filter/competitor_intent/__init__.py
litellm/proxy/guardrails/guardrail_hooks/litellm_content_filter/competitor_intent/airline.py
litellm/proxy/guardrails/guardrail_hooks/litellm_content_filter/competitor_intent/base.py
litellm/proxy/guardrails/guardrail_hooks/litellm_content_filter/content_filter.py
litellm/proxy/guardrails/guardrail_hooks/litellm_content_filter/guardrail_benchmarks/test_eval.py
litellm/proxy/guardrails/guardrail_hooks/litellm_content_filter/patterns.py
litellm/proxy/guardrails/guardrail_hooks/mcp_end_user_permission/__init__.py
litellm/proxy/guardrails/guardrail_hooks/mcp_end_user_permission/mcp_end_user_permission.py
litellm/proxy/guardrails/guardrail_hooks/mcp_jwt_signer/__init__.py
litellm/proxy/guardrails/guardrail_hooks/mcp_jwt_signer/mcp_jwt_signer.py
litellm/proxy/guardrails/guardrail_hooks/mcp_security/__init__.py
litellm/proxy/guardrails/guardrail_hooks/mcp_security/mcp_security_guardrail.py
litellm/proxy/guardrails/guardrail_hooks/model_armor/__init__.py
litellm/proxy/guardrails/guardrail_hooks/model_armor/model_armor.py
litellm/proxy/guardrails/guardrail_hooks/noma/__init__.py
litellm/proxy/guardrails/guardrail_hooks/noma/noma.py
litellm/proxy/guardrails/guardrail_hooks/noma/noma_v2.py
litellm/proxy/guardrails/guardrail_hooks/onyx/__init__.py
litellm/proxy/guardrails/guardrail_hooks/onyx/onyx.py
litellm/proxy/guardrails/guardrail_hooks/openai/__init__.py
litellm/proxy/guardrails/guardrail_hooks/openai/base.py
litellm/proxy/guardrails/guardrail_hooks/openai/moderations.py
litellm/proxy/guardrails/guardrail_hooks/pangea/__init__.py
litellm/proxy/guardrails/guardrail_hooks/pangea/pangea.py
litellm/proxy/guardrails/guardrail_hooks/panw_prisma_airs/__init__.py
litellm/proxy/guardrails/guardrail_hooks/panw_prisma_airs/panw_prisma_airs.py
litellm/proxy/guardrails/guardrail_hooks/pillar/__init__.py
litellm/proxy/guardrails/guardrail_hooks/pillar/pillar.py
litellm/proxy/guardrails/guardrail_hooks/presidio.py
litellm/proxy/guardrails/guardrail_hooks/prompt_security/__init__.py
litellm/proxy/guardrails/guardrail_hooks/prompt_security/prompt_security.py
litellm/proxy/guardrails/guardrail_hooks/promptguard/__init__.py
litellm/proxy/guardrails/guardrail_hooks/promptguard/promptguard.py
litellm/proxy/guardrails/guardrail_hooks/qualifire/__init__.py
litellm/proxy/guardrails/guardrail_hooks/qualifire/qualifire.py
litellm/proxy/guardrails/guardrail_hooks/semantic_guard/__init__.py
litellm/proxy/guardrails/guardrail_hooks/semantic_guard/route_loader.py
litellm/proxy/guardrails/guardrail_hooks/semantic_guard/semantic_guard.py
litellm/proxy/guardrails/guardrail_hooks/tool_permission.py
litellm/proxy/guardrails/guardrail_hooks/tool_policy/__init__.py
litellm/proxy/guardrails/guardrail_hooks/tool_policy/tool_policy_guardrail.py
litellm/proxy/guardrails/guardrail_hooks/unified_guardrail/__init__.py
litellm/proxy/guardrails/guardrail_hooks/unified_guardrail/unified_guardrail.py
litellm/proxy/guardrails/guardrail_hooks/zscaler_ai_guard/__init__.py
litellm/proxy/guardrails/guardrail_hooks/zscaler_ai_guard/zscaler_ai_guard.py
litellm/proxy/guardrails/guardrail_initializers.py
litellm/proxy/guardrails/guardrail_registry.py
litellm/proxy/guardrails/init_guardrails.py
litellm/proxy/guardrails/tool_name_extraction.py
litellm/proxy/guardrails/usage_endpoints.py
litellm/proxy/guardrails/usage_tracking.py
litellm/proxy/health_check.py
litellm/proxy/health_check_utils/__init__.py
litellm/proxy/health_check_utils/shared_health_check_manager.py
litellm/proxy/health_endpoints/_health_endpoints.py
litellm/proxy/health_endpoints/health_app_factory.py
litellm/proxy/hooks/__init__.py
litellm/proxy/hooks/azure_content_safety.py
litellm/proxy/hooks/batch_rate_limiter.py
litellm/proxy/hooks/batch_redis_get.py
litellm/proxy/hooks/cache_control_check.py
litellm/proxy/hooks/dynamic_rate_limiter.py
litellm/proxy/hooks/dynamic_rate_limiter_v3.py
litellm/proxy/hooks/key_management_event_hooks.py
litellm/proxy/hooks/litellm_skills/__init__.py
litellm/proxy/hooks/litellm_skills/main.py
litellm/proxy/hooks/max_budget_limiter.py
litellm/proxy/hooks/max_budget_per_session_limiter.py
litellm/proxy/hooks/max_iterations_limiter.py
litellm/proxy/hooks/mcp_semantic_filter/__init__.py
litellm/proxy/hooks/mcp_semantic_filter/hook.py
litellm/proxy/hooks/model_max_budget_limiter.py
litellm/proxy/hooks/parallel_request_limiter.py
litellm/proxy/hooks/parallel_request_limiter_v3.py
litellm/proxy/hooks/prompt_injection_detection.py
litellm/proxy/hooks/proxy_track_cost_callback.py
litellm/proxy/hooks/rate_limiter_utils.py
litellm/proxy/hooks/responses_id_security.py
litellm/proxy/hooks/user_management_event_hooks.py
litellm/proxy/image_endpoints/__init__.py
litellm/proxy/image_endpoints/endpoints.py
litellm/proxy/lambda.py
litellm/proxy/litellm_pre_call_utils.py
litellm/proxy/management_endpoints/access_group_endpoints.py
litellm/proxy/management_endpoints/budget_management_endpoints.py
litellm/proxy/management_endpoints/cache_settings_endpoints.py
litellm/proxy/management_endpoints/callback_management_endpoints.py
litellm/proxy/management_endpoints/common_daily_activity.py
litellm/proxy/management_endpoints/common_utils.py
litellm/proxy/management_endpoints/compliance_endpoints.py
litellm/proxy/management_endpoints/config_override_endpoints.py
litellm/proxy/management_endpoints/cost_tracking_settings.py
litellm/proxy/management_endpoints/customer_endpoints.py
litellm/proxy/management_endpoints/fallback_management_endpoints.py
litellm/proxy/management_endpoints/internal_user_endpoints.py
litellm/proxy/management_endpoints/jwt_key_mapping_endpoints.py
litellm/proxy/management_endpoints/key_management_endpoints.py
litellm/proxy/management_endpoints/mcp_management_endpoints.py
litellm/proxy/management_endpoints/model_access_group_management_endpoints.py
litellm/proxy/management_endpoints/model_management_endpoints.py
litellm/proxy/management_endpoints/organization_endpoints.py
litellm/proxy/management_endpoints/policy_endpoints/__init__.py
litellm/proxy/management_endpoints/policy_endpoints/ai_policy_suggester.py
litellm/proxy/management_endpoints/policy_endpoints/endpoints.py
litellm/proxy/management_endpoints/project_endpoints.py
litellm/proxy/management_endpoints/router_settings_endpoints.py
litellm/proxy/management_endpoints/scim/scim_transformations.py
litellm/proxy/management_endpoints/scim/scim_v2.py
litellm/proxy/management_endpoints/sso/__init__.py
litellm/proxy/management_endpoints/sso/custom_microsoft_sso.py
litellm/proxy/management_endpoints/sso_helper_utils.py
litellm/proxy/management_endpoints/tag_management_endpoints.py
litellm/proxy/management_endpoints/team_callback_endpoints.py
litellm/proxy/management_endpoints/team_endpoints.py
litellm/proxy/management_endpoints/tool_management_endpoints.py
litellm/proxy/management_endpoints/types.py
litellm/proxy/management_endpoints/ui_sso.py
litellm/proxy/management_endpoints/usage_endpoints/__init__.py
litellm/proxy/management_endpoints/usage_endpoints/ai_usage_chat.py
litellm/proxy/management_endpoints/usage_endpoints/endpoints.py
litellm/proxy/management_endpoints/user_agent_analytics_endpoints.py
litellm/proxy/management_helpers/audit_logs.py
litellm/proxy/management_helpers/object_permission_utils.py
litellm/proxy/management_helpers/team_member_permission_checks.py
litellm/proxy/management_helpers/user_invitation.py
litellm/proxy/management_helpers/utils.py
litellm/proxy/mcp_tools.py
litellm/proxy/middleware/in_flight_requests_middleware.py
litellm/proxy/middleware/prometheus_auth_middleware.py
litellm/proxy/ocr_endpoints/__init__.py
litellm/proxy/ocr_endpoints/endpoints.py
litellm/proxy/openai_evals_endpoints/__init__.py
litellm/proxy/openai_evals_endpoints/endpoints.py
litellm/proxy/openai_files_endpoints/common_utils.py
litellm/proxy/openai_files_endpoints/file_content_streaming_handler.py
litellm/proxy/openai_files_endpoints/files_endpoints.py
litellm/proxy/openai_files_endpoints/storage_backend_service.py
litellm/proxy/pass_through_endpoints/common_utils.py
litellm/proxy/pass_through_endpoints/jsonpath_extractor.py
litellm/proxy/pass_through_endpoints/llm_passthrough_endpoints.py
litellm/proxy/pass_through_endpoints/llm_provider_handlers/anthropic_passthrough_logging_handler.py
litellm/proxy/pass_through_endpoints/llm_provider_handlers/assembly_passthrough_logging_handler.py
litellm/proxy/pass_through_endpoints/llm_provider_handlers/base_passthrough_logging_handler.py
litellm/proxy/pass_through_endpoints/llm_provider_handlers/cohere_passthrough_logging_handler.py
litellm/proxy/pass_through_endpoints/llm_provider_handlers/cursor_passthrough_logging_handler.py
litellm/proxy/pass_through_endpoints/llm_provider_handlers/gemini_passthrough_logging_handler.py
litellm/proxy/pass_through_endpoints/llm_provider_handlers/openai_passthrough_logging_handler.py
litellm/proxy/pass_through_endpoints/llm_provider_handlers/vertex_ai_live_passthrough_logging_handler.py
litellm/proxy/pass_through_endpoints/llm_provider_handlers/vertex_passthrough_logging_handler.py
litellm/proxy/pass_through_endpoints/pass_through_endpoints.py
litellm/proxy/pass_through_endpoints/passthrough_endpoint_router.py
litellm/proxy/pass_through_endpoints/passthrough_guardrails.py
litellm/proxy/pass_through_endpoints/streaming_handler.py
litellm/proxy/pass_through_endpoints/success_handler.py
litellm/proxy/policy_engine/__init__.py
litellm/proxy/policy_engine/attachment_registry.py
litellm/proxy/policy_engine/condition_evaluator.py
litellm/proxy/policy_engine/init_policies.py
litellm/proxy/policy_engine/pipeline_executor.py
litellm/proxy/policy_engine/policy_endpoints.py
litellm/proxy/policy_engine/policy_matcher.py
litellm/proxy/policy_engine/policy_registry.py
litellm/proxy/policy_engine/policy_resolve_endpoints.py
litellm/proxy/policy_engine/policy_resolver.py
litellm/proxy/policy_engine/policy_validator.py
litellm/proxy/post_call_rules.py
litellm/proxy/prisma_migration.py
litellm/proxy/prometheus_cleanup.py
litellm/proxy/prompts/__init__.py
litellm/proxy/prompts/init_prompts.py
litellm/proxy/prompts/prompt_endpoints.py
litellm/proxy/prompts/prompt_registry.py
litellm/proxy/proxy_cli.py
litellm/proxy/proxy_server.py
litellm/proxy/public_endpoints/__init__.py
litellm/proxy/public_endpoints/public_endpoints.py
litellm/proxy/rag_endpoints/__init__.py
litellm/proxy/rag_endpoints/endpoints.py
litellm/proxy/realtime_endpoints/__init__.py
litellm/proxy/realtime_endpoints/endpoints.py
litellm/proxy/rerank_endpoints/endpoints.py
litellm/proxy/response_api_endpoints/endpoints.py
litellm/proxy/response_polling/__init__.py
litellm/proxy/response_polling/background_streaming.py
litellm/proxy/response_polling/polling_handler.py
litellm/proxy/route_llm_request.py
litellm/proxy/search_endpoints/__init__.py
litellm/proxy/search_endpoints/endpoints.py
litellm/proxy/search_endpoints/search_tool_management.py
litellm/proxy/search_endpoints/search_tool_registry.py
litellm/proxy/spend_tracking/cloudzero_endpoints.py
litellm/proxy/spend_tracking/cold_storage_handler.py
litellm/proxy/spend_tracking/spend_management_endpoints.py
litellm/proxy/spend_tracking/spend_tracking_utils.py
litellm/proxy/spend_tracking/vantage_endpoints.py
litellm/proxy/types_utils/utils.py
litellm/proxy/ui_crud_endpoints/__init__.py
litellm/proxy/ui_crud_endpoints/proxy_setting_endpoints.py
litellm/proxy/utils.py
litellm/proxy/vector_store_endpoints/endpoints.py
litellm/proxy/vector_store_endpoints/management_endpoints.py
litellm/proxy/vector_store_endpoints/utils.py
litellm/proxy/vector_store_files_endpoints/__init__.py
litellm/proxy/vector_store_files_endpoints/endpoints.py
litellm/proxy/vertex_ai_endpoints/langfuse_endpoints.py
litellm/proxy/video_endpoints/__init__.py
litellm/proxy/video_endpoints/endpoints.py
litellm/proxy/video_endpoints/utils.py
```

The inventory contains 194,943 lines in vuln and 194,963 lines in fixed.

## Frozen-regex scans

All scans were case-insensitive and line-numbered over exactly the 394 paths above, with matches
sorted by byte order.

### Candidate 01 — CWE-502 Deserialization of Untrusted Data

Exact regex:

```text
pickle|marshal|shelve|yaml\.(load|unsafe_load)|gob\.newdecoder|deserialize|objectinputstream
```

Both revisions have the same 11 matching lines; there is no truncation:

```text
litellm/proxy/_experimental/mcp_server/mcp_server_manager.py:138:def _deserialize_json_dict(data: Any) -> Optional[Dict[str, str]]:
litellm/proxy/_experimental/mcp_server/mcp_server_manager.py:140:    Deserialize optional JSON mappings stored in the database.
litellm/proxy/_experimental/mcp_server/mcp_server_manager.py:553:        env_dict = _deserialize_json_dict(getattr(mcp_server, "env", None))
litellm/proxy/_experimental/mcp_server/mcp_server_manager.py:554:        static_headers_dict = _deserialize_json_dict(
litellm/proxy/_experimental/mcp_server/mcp_server_manager.py:557:        credentials_dict = _deserialize_json_dict(
litellm/proxy/_experimental/mcp_server/mcp_server_manager.py:679:            tool_name_to_display_name=_deserialize_json_dict(
litellm/proxy/_experimental/mcp_server/mcp_server_manager.py:682:            tool_name_to_description=_deserialize_json_dict(
litellm/proxy/management_endpoints/key_management_endpoints.py:3097:            # Deserialize router_settings from JSON string to dict for response
litellm/proxy/management_endpoints/team_endpoints.py:326:        # on how the team was fetched/deserialized.
litellm/proxy/spend_tracking/spend_tracking_utils.py:707:    This avoids pickle-based deepcopy which fails on Pydantic v2 models
litellm/proxy/spend_tracking/spend_tracking_utils.py:737:            # Use Pydantic's model_dump() instead of pickle
```

The named implementation parses JSON strings and otherwise returns already-materialized values:

```python
def _deserialize_json_dict(data: Any) -> Optional[Dict[str, str]]:
    """
    Deserialize optional JSON mappings stored in the database.

    Accepts values kept as JSON strings or materialized dictionaries and
    returns None when the input is empty or cannot be decoded.
    """
    if not data:
        return None

    if isinstance(data, str):
        try:
            return json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return None
    else:
        return data
```

The router-settings conversion mentioned by the other implementation comment is:

```python
router_settings_value = key_data.get("router_settings")
if router_settings_value is not None and isinstance(router_settings_value, str):
    try:
        key_data["router_settings"] = yaml.safe_load(router_settings_value)
    except yaml.YAMLError:
        ...
```

The pickle mentions are comments explaining that the code uses a JSON-serializable recursive
conversion and Pydantic model_dump instead of pickle.

### Candidate 02 — CWE-601 Open Redirect

Exact regex:

```text
redirect|location[[:space:]]*:|http\.redirect|redirectresponse
```

Both revisions have 205 matching lines. The sorted output is explicitly truncated after the first
20 lines (185 further matches omitted in each revision); the first 20 are identical:

```text
litellm/proxy/_experimental/mcp_server/byok_oauth_endpoints.py:12:  POST /v1/mcp/oauth/authorize                       — Stores temp auth code and redirects
litellm/proxy/_experimental/mcp_server/byok_oauth_endpoints.py:26:from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
litellm/proxy/_experimental/mcp_server/byok_oauth_endpoints.py:36:# Each entry: {code: {api_key, server_id, code_challenge, redirect_uri, user_id, expires_at}}
litellm/proxy/_experimental/mcp_server/byok_oauth_endpoints.py:438:      <input type="hidden" name="redirect_uri"          value="{redirect_uri}">
litellm/proxy/_experimental/mcp_server/byok_oauth_endpoints.py:573:    redirect_uri: Optional[str] = None,
litellm/proxy/_experimental/mcp_server/byok_oauth_endpoints.py:588:    if not redirect_uri:
litellm/proxy/_experimental/mcp_server/byok_oauth_endpoints.py:589:        raise HTTPException(status_code=400, detail="redirect_uri is required")
litellm/proxy/_experimental/mcp_server/byok_oauth_endpoints.py:618:        redirect_uri=redirect_uri,
litellm/proxy/_experimental/mcp_server/byok_oauth_endpoints.py:633:    redirect_uri: str = Form(...),
litellm/proxy/_experimental/mcp_server/byok_oauth_endpoints.py:639:) -> RedirectResponse:
litellm/proxy/_experimental/mcp_server/byok_oauth_endpoints.py:643:    Stores a short-lived authorization code and redirects the client back to
litellm/proxy/_experimental/mcp_server/byok_oauth_endpoints.py:644:    redirect_uri with ?code=...&state=... query parameters.
litellm/proxy/_experimental/mcp_server/byok_oauth_endpoints.py:648:    # Validate redirect_uri scheme to prevent open redirect
litellm/proxy/_experimental/mcp_server/byok_oauth_endpoints.py:649:    parsed_uri = urlparse(redirect_uri)
litellm/proxy/_experimental/mcp_server/byok_oauth_endpoints.py:651:        raise HTTPException(status_code=400, detail="Invalid redirect_uri scheme")
litellm/proxy/_experimental/mcp_server/byok_oauth_endpoints.py:670:        "redirect_uri": redirect_uri,
litellm/proxy/_experimental/mcp_server/byok_oauth_endpoints.py:676:    separator = "&" if "?" in redirect_uri else "?"
litellm/proxy/_experimental/mcp_server/byok_oauth_endpoints.py:677:    location = f"{redirect_uri}{separator}{params}"
litellm/proxy/_experimental/mcp_server/byok_oauth_endpoints.py:678:    return RedirectResponse(url=location, status_code=302)
litellm/proxy/_experimental/mcp_server/byok_oauth_endpoints.py:691:    redirect_uri: str = Form(default=""),
```

The same module's router is imported and mounted on the proxy application:

```python
from litellm.proxy._experimental.mcp_server.byok_oauth_endpoints import (
    router as mcp_byok_oauth_router,
)
...
app.include_router(mcp_byok_oauth_router)
```

The unchanged POST endpoint accepts redirect_uri directly as a form field. Its only redirect-URI
validation restricts the scheme to HTTP or HTTPS; it does not constrain the host or bind the value
to a registered URI:

```python
@router.post("/v1/mcp/oauth/authorize", include_in_schema=False)
async def byok_authorize_post(
    request: Request,
    client_id: str = Form(default=""),
    redirect_uri: str = Form(...),
    code_challenge: str = Form(...),
    code_challenge_method: str = Form(default="S256"),
    state: str = Form(default=""),
    server_id: str = Form(default=""),
    api_key: str = Form(...),
) -> RedirectResponse:
    _purge_expired_codes()

    parsed_uri = urlparse(redirect_uri)
    if parsed_uri.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="Invalid redirect_uri scheme")

    if len(_byok_auth_codes) >= _AUTH_CODES_MAX_SIZE:
        raise HTTPException(
            status_code=503, detail="Too many pending authorization flows"
        )

    if code_challenge_method != "S256":
        raise HTTPException(
            status_code=400, detail="Only S256 code_challenge_method is supported"
        )

    auth_code = str(uuid.uuid4())
    _byok_auth_codes[auth_code] = {
        "api_key": api_key,
        "server_id": server_id,
        "code_challenge": code_challenge,
        "redirect_uri": redirect_uri,
        "user_id": client_id,
        "expires_at": time.time() + _AUTH_CODE_TTL_SECONDS,
    }

    params = urlencode({"code": auth_code, "state": state})
    separator = "&" if "?" in redirect_uri else "?"
    location = f"{redirect_uri}{separator}{params}"
    return RedirectResponse(url=location, status_code=302)
```

### Candidate 03 — CWE-611 XML External Entity

Exact regex:

```text
xxe|external.*entity|resolve_entities|load_dtd|no_network|xml\.decoder|etree|xmlparser
```

Both revisions have the same single matching line; there is no truncation:

```text
litellm/proxy/_experimental/mcp_server/server.py:2014:                # External auth header supplied; still enforce user-identity check.
```

The surrounding unchanged code shows that this is a comment in an authentication branch, not XML
or entity processing:

```python
elif mcp_server.is_byok:
    # External auth header supplied; still enforce user-identity check.
    await _check_byok_credential(mcp_server, user_api_key_auth)
```

---

Return exactly this schema with all labels replaced, and no Markdown fence or prose:

labels:
  candidate-01: {vuln: LABEL, fixed: LABEL}
  candidate-02: {vuln: LABEL, fixed: LABEL}
  candidate-03: {vuln: LABEL, fixed: LABEL}

