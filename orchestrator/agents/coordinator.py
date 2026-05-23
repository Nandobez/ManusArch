"""
Coordinator - Camada de coordenação (Orquestrador principal)
Responsável por:
- Decomposição de tarefas
- Atribuição para agentes especializados
- Gerenciamento de memória/conhecimento
- Combinação de resultados
"""

import json
import uuid
from typing import Optional
from dataclasses import dataclass, field
from .base import BaseAgent, Task, TaskResult


@dataclass
class Memory:
    """Memória compartilhada entre agentes"""
    facts: list = field(default_factory=list)
    context: dict = field(default_factory=dict)
    conversation_history: list = field(default_factory=list)
    task_results: list = field(default_factory=list)

    def add_fact(self, fact: str):
        self.facts.append(fact)

    def add_result(self, result: TaskResult):
        self.task_results.append(result.to_dict())

    def get_context_summary(self) -> str:
        """Retorna resumo do contexto para o LLM"""
        summary = []

        if self.facts:
            summary.append("Fatos conhecidos:")
            for f in self.facts[-10:]:  # Últimos 10 fatos
                summary.append(f"  - {f}")

        if self.task_results:
            summary.append("\nResultados anteriores:")
            for r in self.task_results[-5:]:  # Últimos 5 resultados
                status = "✓" if r["success"] else "✗"
                summary.append(f"  {status} [{r['agent_name']}] {r['message'][:100]}")

        return "\n".join(summary) if summary else "Nenhum contexto anterior."


DECOMPOSITION_PROMPT = """Você é um coordenador de agentes especializados. Analise a tarefa e decomponha em subtarefas.

<agentes_disponiveis>
1. WebAgent - Navegação web completa: abre sites, busca, clica, extrai dados
2. CodeAgent - Criação de código Python/HTML/CSS e execução
3. DataAgent - Análise de dados, chamadas de API, processamento
4. FileAgent - Gerenciamento de arquivos, leitura, escrita
</agentes_disponiveis>

<REGRA_IMPORTANTE>
⚠️ CRIE NO MÁXIMO 3 SUBTAREFAS
⚠️ Agrupe ações relacionadas em UMA subtarefa
⚠️ WebAgent faz TODO o trabalho web de uma vez (navegar + clicar + extrair)
⚠️ CodeAgent cria HTML/código E abre no browser
</REGRA_IMPORTANTE>

<exemplo_CORRETO>
Tarefa: "Abra YouTube, busque X, pegue comentários e faça HTML"
Subtarefas:
1. WebAgent: Navegar ao YouTube, buscar X, abrir vídeo, extrair comentários (TUDO JUNTO)
2. CodeAgent: Criar HTML com os dados extraídos e abrir no browser
</exemplo_CORRETO>

<contexto_projeto>
{project_context}
</contexto_projeto>

<memoria>
{memory_context}
</memoria>

<tarefa>
{task}
</tarefa>

Responda APENAS com JSON válido no formato:
{{
    "analysis": "Breve análise",
    "subtasks": [
        {{
            "id": "1",
            "description": "Descrição completa da subtarefa",
            "agent": "WebAgent|CodeAgent|DataAgent|FileAgent",
            "priority": 1,
            "depends_on": []
        }}
    ],
    "final_output": "O que será entregue"
}}
"""


class Coordinator:
    """Coordenador principal - orquestra múltiplos agentes"""

    def __init__(self, llm_client, executor, project_manager):
        self.llm = llm_client
        self.executor = executor
        self.project_manager = project_manager
        self.memory = Memory()
        self.agents: dict[str, BaseAgent] = {}
        self.task_queue: list[Task] = []
        self.completed_tasks: list[Task] = []

    def register_agent(self, agent: BaseAgent):
        """Registra um agente especializado"""
        self.agents[agent.name] = agent
        print(f"  ✓ Agente registrado: {agent.name}")

    def decompose_task(self, task_description: str) -> list[Task]:
        """Decompõe tarefa em subtarefas para agentes específicos"""

        # Obtém contexto
        project = self.project_manager.get_current_project()
        project_context = f"Projeto: {project['name']}\nDiretório: {project['path']}" if project else "Nenhum projeto"
        memory_context = self.memory.get_context_summary()

        # Chama LLM para decomposição
        prompt = DECOMPOSITION_PROMPT.format(
            project_context=project_context,
            memory_context=memory_context,
            task=task_description
        )

        response = self.llm.chat([
            {"role": "system", "content": "Você responde apenas em JSON válido."},
            {"role": "user", "content": prompt}
        ])

        # Parse da resposta
        try:
            # Limpa resposta (remove markdown se houver)
            clean_response = response.strip()
            if clean_response.startswith("```"):
                clean_response = clean_response.split("```")[1]
                if clean_response.startswith("json"):
                    clean_response = clean_response[4:]
            clean_response = clean_response.strip()

            plan = json.loads(clean_response)
        except json.JSONDecodeError as e:
            print(f"Erro ao parsear plano: {e}")
            print(f"Resposta: {response}")
            # Fallback: cria tarefa única
            return [Task(
                id=str(uuid.uuid4())[:8],
                description=task_description,
                agent_type="CodeAgent",
                priority=1
            )]

        # Converte para objetos Task
        tasks = []
        for st in plan.get("subtasks", []):
            task = Task(
                id=st.get("id", str(uuid.uuid4())[:8]),
                description=st.get("description", ""),
                agent_type=st.get("agent", "CodeAgent"),
                priority=st.get("priority", 1),
                dependencies=st.get("depends_on", [])
            )
            tasks.append(task)

        print(f"\n📋 Plano de execução ({len(tasks)} subtarefas):")
        print(f"   Análise: {plan.get('analysis', 'N/A')}")
        for t in tasks:
            deps = f" (depende de: {t.dependencies})" if t.dependencies else ""
            print(f"   [{t.id}] {t.agent_type}: {t.description[:60]}...{deps}")
        print(f"   Output esperado: {plan.get('final_output', 'N/A')}")

        return tasks

    def execute_task(self, task: Task) -> TaskResult:
        """Executa uma tarefa usando o agente apropriado"""

        agent = self.agents.get(task.agent_type)
        if not agent:
            return TaskResult(
                success=False,
                error=f"Agente não encontrado: {task.agent_type}",
                agent_name="Coordinator"
            )

        # Adiciona contexto da memória
        task.context["memory"] = self.memory.get_context_summary()
        task.context["previous_results"] = [
            t.result.to_dict() for t in self.completed_tasks if t.result
        ]

        print(f"\n🤖 Executando [{task.agent_type}]: {task.description[:50]}...")
        task.status = "running"

        try:
            result = agent.execute(task)
            task.status = "completed" if result.success else "failed"
            task.result = result

            # Adiciona à memória
            self.memory.add_result(result)

            return result

        except Exception as e:
            task.status = "failed"
            return TaskResult(
                success=False,
                error=str(e),
                agent_name=task.agent_type
            )

    def run(self, task_description: str) -> dict:
        """Executa uma tarefa completa com decomposição e orquestração"""

        print(f"\n{'='*60}")
        print(f"🎯 TAREFA: {task_description}")
        print(f"{'='*60}")

        # 1. Decompõe a tarefa
        subtasks = self.decompose_task(task_description)
        self.task_queue = subtasks

        # 2. Executa subtarefas em ordem (respeitando dependências)
        results = []
        for task in self.task_queue:
            # Verifica dependências
            if task.dependencies:
                deps_completed = all(
                    any(ct.id == dep and ct.status == "completed" for ct in self.completed_tasks)
                    for dep in task.dependencies
                )
                if not deps_completed:
                    print(f"⏳ Aguardando dependências para [{task.id}]")
                    continue

            result = self.execute_task(task)
            results.append(result)
            self.completed_tasks.append(task)

            if result.success:
                print(f"   ✓ {result.message[:80]}")
            else:
                print(f"   ✗ ERRO: {result.error}")

        # 3. Combina resultados
        combined = self._combine_results(results)

        print(f"\n{'='*60}")
        print(f"📦 RESULTADO FINAL")
        print(f"{'='*60}")
        print(f"Subtarefas: {len(results)} executadas")
        print(f"Sucesso: {sum(1 for r in results if r.success)}/{len(results)}")

        return combined

    def _combine_results(self, results: list[TaskResult]) -> dict:
        """Combina resultados de múltiplas tarefas"""
        return {
            "success": all(r.success for r in results),
            "total_tasks": len(results),
            "completed": sum(1 for r in results if r.success),
            "failed": sum(1 for r in results if not r.success),
            "files_created": [f for r in results for f in r.files_created],
            "files_modified": [f for r in results for f in r.files_modified],
            "messages": [r.message for r in results if r.message],
            "errors": [r.error for r in results if r.error]
        }

    def get_memory(self) -> Memory:
        """Retorna memória compartilhada"""
        return self.memory

    def clear_memory(self):
        """Limpa memória"""
        self.memory = Memory()
        self.completed_tasks = []
