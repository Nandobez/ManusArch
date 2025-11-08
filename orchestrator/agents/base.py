"""
Base Agent - Classe base para todos os agentes especializados
"""

from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime
import json


@dataclass
class TaskResult:
    """Resultado de uma tarefa executada por um agente"""
    success: bool
    data: any = None
    message: str = ""
    files_created: list = field(default_factory=list)
    files_modified: list = field(default_factory=list)
    error: Optional[str] = None
    duration_ms: int = 0
    agent_name: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "message": self.message,
            "files_created": self.files_created,
            "files_modified": self.files_modified,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "agent_name": self.agent_name
        }

    def to_context(self) -> str:
        """Converte para string para ser usada como contexto"""
        if self.success:
            return f"[{self.agent_name}] ✓ {self.message}"
        else:
            return f"[{self.agent_name}] ✗ ERRO: {self.error}"


@dataclass
class Task:
    """Representa uma tarefa para um agente"""
    id: str
    description: str
    agent_type: str
    priority: int = 1
    dependencies: list = field(default_factory=list)
    context: dict = field(default_factory=dict)
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[TaskResult] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class BaseAgent(ABC):
    """Classe base para agentes especializados"""

    def __init__(self, name: str, llm_client, executor):
        self.name = name
        self.llm = llm_client
        self.executor = executor
        self.capabilities = []
        self.system_prompt = ""

    @abstractmethod
    def can_handle(self, task_description: str) -> bool:
        """Verifica se o agente pode lidar com a tarefa"""
        pass

    @abstractmethod
    def execute(self, task: Task) -> TaskResult:
        """Executa uma tarefa"""
        pass

    def get_capabilities(self) -> list:
        """Retorna lista de capacidades do agente"""
        return self.capabilities

    def _call_llm(self, messages: list) -> str:
        """Chama o LLM com mensagens"""
        return self.llm.chat(messages)

    def _create_result(self, success: bool, **kwargs) -> TaskResult:
        """Cria resultado padronizado"""
        return TaskResult(
            success=success,
            agent_name=self.name,
            **kwargs
        )
