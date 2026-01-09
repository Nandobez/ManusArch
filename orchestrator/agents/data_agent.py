"""
DataAgent - Especializado em análise de dados e chamadas de API
"""

import re
import json
from .base import BaseAgent, Task, TaskResult

DATA_AGENT_PROMPT = """Você é um agente especializado em análise de dados e integração com APIs.

<capacidades>
- Análise de dados (pandas, numpy)
- Chamadas de API REST
- Processamento de JSON/CSV
- Visualização de dados (matplotlib, plotly)
- Transformação de dados
</capacidades>

<estrutura_projeto>
./src/      - Scripts de análise
./data/     - Dados de entrada (CSV, JSON, etc)
./output/   - Gráficos, relatórios, exports
</estrutura_projeto>

<comandos>
1. Criar script de análise:
```file:./src/analysis.py
import pandas as pd
# código
```

2. Executar:
```shell
python3 ./src/analysis.py
```

3. Testar código rápido:
```python
import requests
response = requests.get("https://api.example.com/data")
print(response.json())
```
</comandos>

<tarefa>
{task_description}
</tarefa>

<contexto>
{context}
</contexto>

<dados_disponiveis>
{available_data}
</dados_disponiveis>

Crie scripts para análise de dados. Salve gráficos em ./output/.
Ao terminar: DONE: <resumo da análise>
"""


class DataAgent(BaseAgent):
    """Agente especializado em dados e APIs"""

    def __init__(self, llm_client, executor):
        super().__init__("DataAgent", llm_client, executor)
        self.capabilities = [
            "data_analysis",
            "api_integration",
            "visualization",
            "csv_processing",
            "json_processing"
        ]

    def can_handle(self, task_description: str) -> bool:
        """Verifica se pode lidar com a tarefa"""
        keywords = [
            "dados", "análise", "analisar", "csv", "json", "api",
            "gráfico", "chart", "visualizar", "estatística", "pandas",
            "tabela", "relatório", "export", "importar"
        ]
        task_lower = task_description.lower()
        return any(kw in task_lower for kw in keywords)

    def execute(self, task: Task) -> TaskResult:
        """Executa tarefa de análise de dados"""

        context = task.context.get("memory", "")

        # Lista dados disponíveis
        available_data = self._list_data_files()

        messages = [
            {"role": "system", "content": DATA_AGENT_PROMPT.format(
                task_description=task.description,
                context=context,
                available_data=available_data
            )}
        ]

        max_iterations = 15
        files_created = []

        for i in range(max_iterations):
            response = self._call_llm(messages)
            messages.append({"role": "assistant", "content": response})

            if "DONE:" in response:
                summary = response.split("DONE:")[-1].strip()
                return self._create_result(
                    success=True,
                    message=summary,
                    files_created=files_created
                )

            result = self._process_action(response, files_created)

            if result:
                messages.append({"role": "user", "content": f"Resultado:\n{result}\n\nContinue ou DONE:"})
            else:
                messages.append({"role": "user", "content": "Execute uma ação ou DONE:"})

        return self._create_result(
            success=False,
            error="Máximo de iterações",
            files_created=files_created
        )

    def _list_data_files(self) -> str:
        """Lista arquivos de dados disponíveis"""
        result = self.executor.execute_shell("find ./data -type f 2>/dev/null | head -20")
        if result.strip():
            return result
        return "Nenhum arquivo em ./data/"

    def _process_action(self, response: str, files_created: list) -> str:
        """Processa ação"""
        import base64
        import subprocess

        # FILE
        file_match = re.search(r'```file:([^\n]+)\n(.*?)```', response, re.DOTALL)
        if file_match:
            filepath = file_match.group(1).strip()
            content = file_match.group(2)
            result = self._create_file(filepath, content)
            files_created.append(filepath)
            return result

        # SHELL
        shell_match = re.search(r'```shell\s*(.*?)```', response, re.DOTALL)
        if shell_match:
            return self.executor.execute_shell(shell_match.group(1).strip())

        # PYTHON
        python_match = re.search(r'```python\s*(.*?)```', response, re.DOTALL)
        if python_match:
            code = python_match.group(1).strip()
            escaped = code.replace("'", "'\\''")
            return self.executor.execute_shell(f"/opt/venv/bin/python3 -c '{escaped}'")

        return None

    def _create_file(self, filepath: str, content: str) -> str:
        """Cria arquivo"""
        import base64
        import subprocess

        working_dir = self.executor.working_dir
        if filepath.startswith("./"):
            full_path = f"{working_dir}/{filepath[2:]}"
        else:
            full_path = f"{working_dir}/{filepath}"

        dir_path = "/".join(full_path.split("/")[:-1])
        self.executor.execute_shell(f"mkdir -p {dir_path}")

        encoded = base64.b64encode(content.encode()).decode()
        command = f"echo '{encoded}' | base64 -d > {full_path}"

        result = subprocess.run(
            ["docker", "exec", self.executor.container, "bash", "-c", command],
            capture_output=True,
            text=True,
            timeout=30
        )

        return f"✅ Arquivo criado: {filepath}" if result.returncode == 0 else f"ERRO: {result.stderr}"
