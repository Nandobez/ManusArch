"""
Cliente LLM - Suporta múltiplos providers (OpenAI, Anthropic, Ollama)
"""

import os
from abc import ABC, abstractmethod


class LLMClient(ABC):
    """Interface base para clientes LLM"""

    @abstractmethod
    def chat(self, messages: list[dict]) -> str:
        """Envia mensagens e retorna resposta"""
        pass


class OpenAIClient(LLMClient):
    """Cliente para OpenAI API (GPT-4, etc)"""

    def __init__(self, model: str = "gpt-4o", api_key: str = None):
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError("Instale: pip install openai")

        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))
        self.model = model

    def chat(self, messages: list[dict]) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=4096
        )
        return response.choices[0].message.content


class AnthropicClient(LLMClient):
    """Cliente para Anthropic API (Claude)"""

    def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: str = None):
        try:
            import anthropic
        except ImportError:
            raise ImportError("Instale: pip install anthropic")

        self.client = anthropic.Anthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))
        self.model = model

    def chat(self, messages: list[dict]) -> str:
        # Anthropic separa system message
        system = ""
        chat_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                chat_messages.append(msg)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=chat_messages
        )
        return response.content[0].text


class OllamaClient(LLMClient):
    """Cliente para Ollama (modelos locais)"""

    def __init__(self, model: str = "llama3.1", host: str = "http://localhost:11434"):
        try:
            import ollama
        except ImportError:
            raise ImportError("Instale: pip install ollama")

        self.client = ollama
        self.model = model
        self.host = host

    def chat(self, messages: list[dict]) -> str:
        response = self.client.chat(
            model=self.model,
            messages=messages
        )
        return response["message"]["content"]


class GroqClient(LLMClient):
    """Cliente para Groq (LLMs rápidos na nuvem)"""

    def __init__(self, model: str = "llama-3.1-70b-versatile", api_key: str = None):
        try:
            from groq import Groq
        except ImportError:
            raise ImportError("Instale: pip install groq")

        self.client = Groq(api_key=api_key or os.getenv("GROQ_API_KEY"))
        self.model = model

    def chat(self, messages: list[dict]) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=4096
        )
        return response.choices[0].message.content


# === CONFIGURAÇÃO ===
# Descomente e configure o provider que você quer usar

def create_client() -> LLMClient:
    """Cria cliente LLM baseado na configuração"""

    # --- OPÇÃO 1: OpenAI ---
    # return OpenAIClient(model="gpt-4o")

    # --- OPÇÃO 2: Anthropic (Claude) ---
    # return AnthropicClient(model="claude-sonnet-4-20250514")

    # --- OPÇÃO 3: Ollama (local) ---
    # return OllamaClient(model="llama3.1")

    # --- OPÇÃO 4: Groq (rápido e barato) ---
    # return GroqClient(model="llama-3.1-70b-versatile")

    # --- ATIVO: DeepSeek via Ollama ---
    return OllamaClient(model="deepseek-v3.1:671b-cloud")
