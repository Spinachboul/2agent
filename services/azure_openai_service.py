from datetime import datetime, timezone
from typing import Any

from openai import AzureOpenAI

from config import get_settings
from services.token_tracker import token_tracker


class AzureService:
    def __init__(self):
        cfg = get_settings()
        
        print("Azure service endpoint:", repr(cfg.azure_openai_endpoint))
        # assign the values manually
        cfg.azure_openai_endpoint = 
        cfg.azure_openai_api_key = 
        cfg.azure_openai_api_version = 
        cfg.azure_openai_deployment = 
        self.cfg = cfg
        # print(
        # "Azure endpoint:",
        # repr(cfg.azure_openai_endpoint),
        # )
        # print(
        #     "Azure deployment configured:",
        #     bool(cfg.azure_openai_deployment),
        # )
        # print(
        #     "Azure API version configured:",
        #     bool(cfg.azure_openai_api_version),
        # )
        self.client = AzureOpenAI(
            azure_endpoint=cfg.azure_openai_endpoint,
            api_key=cfg.azure_openai_api_key,
            api_version=cfg.azure_openai_api_version,
            max_retries = 2,
            timeout =  30.0,
        )

    def invoke(
        self,
        *,
        agent_name: str,
        session_id: str,
        messages: list[dict[str, str]],
        response_format: dict | None = None,
        temperature: float = 0,
    ) -> str:
        kwargs: dict[str, Any] = {
            "model": self.cfg.azure_openai_deployment,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format:
            kwargs["response_format"] = response_format

        response = self.client.chat.completions.create(**kwargs)

        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0

        # Prices are USD per 1 million tokens.
        cost = (
            input_tokens * self.cfg.azure_input_price_per_1m
            + output_tokens * self.cfg.azure_output_price_per_1m
        ) / 1_000_000

        token_tracker.record(session_id, {
            "agent_name": agent_name,
            "model": self.cfg.azure_openai_deployment,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "cost": cost,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "status": "success",
        })

        content = response.choices[0].message.content
        if not content:
            raise RuntimeError(
                f"{agent_name} returned an empty response"
            )
        return content


azure_service = AzureService()
