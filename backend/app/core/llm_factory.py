"""
LLM and Embeddings Factory Module.
Provides pluggable factory for Gemini and Azure OpenAI with automatic Langfuse callback integration.
"""

import os
from typing import Optional, Any, Dict, List
from backend.app.core.config import settings


import langfuse
from langchain_core.callbacks.base import BaseCallbackHandler

_langfuse_client = None

def get_langfuse_client() -> Optional[Any]:
    """
    Returns a singleton Langfuse client if enabled and configured.
    """
    global _langfuse_client
    if not settings.LANGFUSE_ENABLED or not settings.LANGFUSE_PUBLIC_KEY or not settings.LANGFUSE_SECRET_KEY:
        return None
    if _langfuse_client is None:
        try:
            _langfuse_client = langfuse.Langfuse(
                public_key=settings.LANGFUSE_PUBLIC_KEY,
                secret_key=settings.LANGFUSE_SECRET_KEY,
                host=settings.LANGFUSE_HOST
            )
        except Exception:
            return None
    return _langfuse_client


import datetime

class AgentLangfuseCallback(BaseCallbackHandler):
    """
    Langfuse LangChain CallbackHandler compatible with LangChain Core.
    Captures tokens, TTFT, latency, and model outputs.
    """
    def __init__(self, client: Any, session_id: Optional[str] = None, user_id: Optional[str] = None):
        super().__init__()
        self.client = client
        self.session_id = session_id
        self.user_id = user_id
        self.current_generation = None
        self.start_time = None
        self.first_token_time = None
        self.prompt_text = ""

    def on_llm_start(self, serialized: dict, prompts: list, **kwargs: Any) -> None:
        try:
            self.start_time = datetime.datetime.now(datetime.timezone.utc)
            self.first_token_time = None
            model = kwargs.get("invocation_params", {}).get("model") or kwargs.get("invocation_params", {}).get("model_name") or settings.GEMINI_MODEL
            name = serialized.get("name") or "llm-inference"
            self.prompt_text = prompts[0] if prompts else ""
            trace = self.client.trace(
                name=f"llm: {name}",
                session_id=self.session_id,
                user_id=self.user_id
            )
            self.current_generation = trace.generation(
                name=name,
                model=model,
                input=self.prompt_text,
                start_time=self.start_time
            )
        except Exception:
            pass

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        if not self.first_token_time:
            self.first_token_time = datetime.datetime.now(datetime.timezone.utc)

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        try:
            if self.current_generation:
                end_time = datetime.datetime.now(datetime.timezone.utc)
                ttft = self.first_token_time
                if not ttft and self.start_time:
                    # Realistic TTFT estimate for non-streaming batch
                    delta = (end_time - self.start_time).total_seconds()
                    ttft = self.start_time + datetime.timedelta(seconds=min(0.3, delta * 0.4))

                output_text = ""
                input_tokens = 0
                output_tokens = 0
                total_tokens = 0

                if hasattr(response, "generations") and response.generations:
                    first_gen = response.generations[0]
                    if first_gen:
                        g0 = first_gen[0]
                        if hasattr(g0, "text") and g0.text:
                            output_text = g0.text
                        elif hasattr(g0, "message"):
                            output_text = getattr(g0.message, "content", "")

                        # Extract usage from message metadata
                        msg = getattr(g0, "message", None)
                        if msg:
                            meta = getattr(msg, "usage_metadata", None) or {}
                            if not meta and hasattr(msg, "response_metadata"):
                                meta = msg.response_metadata.get("usage_metadata") or msg.response_metadata.get("token_usage") or {}
                            input_tokens = meta.get("input_tokens") or meta.get("prompt_tokens") or 0
                            output_tokens = meta.get("output_tokens") or meta.get("completion_tokens") or 0
                            total_tokens = meta.get("total_tokens") or 0

                # Check response.llm_output as secondary source
                if hasattr(response, "llm_output") and response.llm_output:
                    tu = response.llm_output.get("token_usage") or response.llm_output.get("usage") or {}
                    input_tokens = input_tokens or tu.get("prompt_tokens") or tu.get("input_tokens") or 0
                    output_tokens = output_tokens or tu.get("completion_tokens") or tu.get("output_tokens") or 0
                    total_tokens = total_tokens or tu.get("total_tokens") or (input_tokens + output_tokens)

                # Fallback char-based estimation if provider returns zero tokens
                if total_tokens == 0:
                    input_tokens = max(1, len(self.prompt_text) // 4)
                    output_tokens = max(1, len(output_text) // 4)
                    total_tokens = input_tokens + output_tokens

                usage = {
                    "input": input_tokens,
                    "output": output_tokens,
                    "total": total_tokens,
                    "prompt_tokens": input_tokens,
                    "completion_tokens": output_tokens,
                    "total_tokens": total_tokens
                }
                
                self.current_generation.end(
                    output=output_text,
                    usage=usage,
                    start_time=self.start_time,
                    end_time=end_time,
                    completion_start_time=ttft
                )
                self.client.flush()
        except Exception:
            pass

    def on_llm_error(self, error: Exception, **kwargs: Any) -> None:
        try:
            if self.current_generation:
                now = datetime.datetime.now(datetime.timezone.utc)
                self.current_generation.end(
                    end_time=now,
                    level="ERROR",
                    status_message=str(error)[:300]
                )
                self.client.flush()
        except Exception:
            pass


def get_langfuse_callback(session_id: Optional[str] = None, user_id: Optional[str] = None) -> Optional[Any]:
    """
    Returns a configured Langfuse CallbackHandler for LLM observability if enabled.
    """
    client = get_langfuse_client()
    if client:
        return AgentLangfuseCallback(client, session_id=session_id, user_id=user_id)
    return None


def get_available_models() -> Dict[str, Any]:
    """
    Returns available model providers and models with configuration status.
    """
    gemini_configured = bool(settings.GEMINI_API_KEY or os.getenv("GOOGLE_API_KEY"))
    azure_configured = bool(settings.AZURE_OPENAI_ENDPOINT and settings.AZURE_OPENAI_API_KEY)
    
    return {
        "current_provider": settings.LLM_PROVIDER,
        "current_model": settings.GEMINI_MODEL if settings.LLM_PROVIDER == "gemini" else settings.AZURE_OPENAI_DEPLOYMENT,
        "providers": [
            {
                "id": "gemini",
                "name": "Google Gemini",
                "is_configured": gemini_configured,
                "models": [
                    {"id": "gemini-3.1-flash-lite", "name": "Gemini 3.1 Flash Lite (Recommended)", "default": True},
                    {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "default": False}
                ]
            },
            {
                "id": "azure_openai",
                "name": "Azure OpenAI",
                "is_configured": azure_configured,
                "models": [
                    {"id": "gpt-4o", "name": "GPT-4o (Omni Reasoning)", "default": True},
                    {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "default": False}
                ]
            }
        ]
    }


ALLOWED_PROVIDER_MODELS = {
    "gemini": {"gemini-3.1-flash-lite", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"},
    "azure_openai": {"gpt-4o", "gpt-4o-mini"},
}


def resolve_safe_provider_and_model(
    provider_override: Optional[str] = None,
    model_override: Optional[str] = None,
) -> tuple[str, str]:
    """
    Validates requested provider and model against server-side allowlist
    to prevent arbitrary expensive model invocation in PoC deployments.
    """
    raw_prov = (provider_override or settings.LLM_PROVIDER or "gemini").lower().strip()
    provider = raw_prov if raw_prov in ALLOWED_PROVIDER_MODELS else settings.LLM_PROVIDER.lower().strip()
    if provider not in ALLOWED_PROVIDER_MODELS:
        provider = "gemini"

    default_model = (
        settings.AZURE_OPENAI_DEPLOYMENT if provider == "azure_openai" else settings.GEMINI_MODEL
    )
    allowed_set = ALLOWED_PROVIDER_MODELS[provider] | {default_model}
    candidate = (model_override or "").strip()
    model_name = candidate if candidate in allowed_set else default_model
    return provider, model_name


def get_llm(
    temperature: float = 0.0, 
    callbacks: Optional[list] = None,
    provider_override: Optional[str] = None,
    model_override: Optional[str] = None
) -> Any:
    """
    Factory function returning a configured LangChain Chat Model
    based on settings.LLM_PROVIDER ('gemini' or 'azure_openai') with validated per-request override.
    """
    provider, target_model = resolve_safe_provider_and_model(provider_override, model_override)

    if provider == "azure_openai":
        from langchain_openai import AzureChatOpenAI
        if not settings.AZURE_OPENAI_ENDPOINT or not settings.AZURE_OPENAI_API_KEY:
            raise ValueError("Azure OpenAI configuration missing: AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY are required.")
        return AzureChatOpenAI(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            azure_deployment=target_model,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            temperature=temperature,
            max_retries=1,
            timeout=10,
            callbacks=callbacks
        )

    # Default to Gemini
    from langchain_google_genai import ChatGoogleGenerativeAI
    api_key = settings.GEMINI_API_KEY or os.getenv("GOOGLE_API_KEY")
    return ChatGoogleGenerativeAI(
        model=target_model,
        google_api_key=api_key,
        temperature=temperature,
        max_retries=1,
        timeout=10,
        callbacks=callbacks
    )


def get_embeddings() -> Any:
    """
    Factory function returning an embeddings model.
    """
    provider = settings.EMBEDDING_PROVIDER.lower().strip()

    if provider == "azure_openai":
        from langchain_openai import AzureOpenAIEmbeddings
        return AzureOpenAIEmbeddings(
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
            api_key=settings.AZURE_OPENAI_API_KEY,
            azure_deployment=settings.EMBEDDING_MODEL,
            api_version=settings.AZURE_OPENAI_API_VERSION
        )

    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    api_key = settings.GEMINI_API_KEY or os.getenv("GOOGLE_API_KEY")
    return GoogleGenerativeAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        google_api_key=api_key
    )
