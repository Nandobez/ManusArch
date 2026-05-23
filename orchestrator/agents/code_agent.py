"""
CodeAgent - Especializado em criação e execução de código Python
"""

import re
import json
import base64
import subprocess
from .base import BaseAgent, Task, TaskResult

CODE_AGENT_PROMPT = """Você é um agente especializado em criar e executar código Python e HTML.

<capacidades>
- Criar scripts Python
- Criar arquivos HTML/CSS/JS
- Executar código
- Abrir arquivos HTML no browser
- Processar dados com Python
</capacidades>

<estrutura_projeto>
./src/      - Scripts Python
./web/      - HTML, CSS, JS
./data/     - Dados de entrada
./output/   - Resultados
</estrutura_projeto>

<comandos>
1. Criar arquivo:
```file:./src/meu_script.py
# código aqui
```

2. Criar HTML:
```file:./web/pagina.html
<!DOCTYPE html>
<html>...</html>
```

3. Executar comando shell:
```shell
python3 ./src/meu_script.py
```

4. Executar Python rápido:
```python
print("Hello")
```

5. Abrir HTML no browser (APÓS criar o arquivo):
```browser
{{"action": "goto", "params": {{"url": "file:///workspace/projects/NOME_PROJETO/web/arquivo.html"}}}}
```
</comandos>

<tarefa>
{task_description}
</tarefa>

<contexto>
{context}
</contexto>

<dados_extraidos>
{extracted_data}
</dados_extraidos>

⚠️ IMPORTANTE: Se houver dados extraídos acima, USE-OS no código que criar.
Nunca invente dados. Use APENAS os dados fornecidos em <dados_extraidos>.

Crie o código necessário. Use ```file: para criar arquivos e ```shell para executar.
Ao terminar, responda: DONE: <resumo>
"""


class CodeAgent(BaseAgent):
    """Agente especializado em código Python"""

    def __init__(self, llm_client, executor):
        super().__init__("CodeAgent", llm_client, executor)
        self.capabilities = [
            "python",
            "scripting",
            "automation",
            "data_processing",
            "code_generation"
        ]

    def can_handle(self, task_description: str) -> bool:
        """Verifica se pode lidar com a tarefa"""
        keywords = [
            "código", "script", "python", "programar", "criar",
            "função", "classe", "automatizar", "executar", "rodar",
            "processar", "calcular", "gerar"
        ]
        task_lower = task_description.lower()
        return any(kw in task_lower for kw in keywords)

    def execute(self, task: Task) -> TaskResult:
        """Executa tarefa de código"""

        context = task.context.get("memory", "")
        previous = task.context.get("previous_results", [])

        # Adiciona resultados anteriores ao contexto
        if previous:
            context += "\n\nResultados anteriores:\n"
            for r in previous[-3:]:
                context += f"- [{r.get('agent_name')}]: {r.get('message', '')[:100]}\n"

        # Extrai dados coletados pelos agentes anteriores
        extracted_data = "Nenhum dado extraído ainda."
        if previous:
            for r in previous:
                data = r.get("data")
                if data and isinstance(data, dict):
                    if "extracted" in data:
                        extracted_data = json.dumps(data["extracted"], indent=2, ensure_ascii=False)
                        break

        messages = [
            {"role": "system", "content": CODE_AGENT_PROMPT.format(
                task_description=task.description,
                context=context,
                extracted_data=extracted_data
            )}
        ]

        max_iterations = 15
        files_created = []
        files_modified = []

        for i in range(max_iterations):
            response = self._call_llm(messages)
            messages.append({"role": "assistant", "content": response})

            # Verifica se terminou
            if "DONE:" in response:
                summary = response.split("DONE:")[-1].strip()
                return self._create_result(
                    success=True,
                    message=summary,
                    files_created=files_created,
                    files_modified=files_modified
                )

            # Processa ação
            result = self._process_action(response, files_created, files_modified)

            if result:
                messages.append({"role": "user", "content": f"Resultado:\n{result}\n\nContinue ou finalize com DONE:"})
            else:
                messages.append({"role": "user", "content": "Execute uma ação (```file:, ```shell, ```python) ou finalize com DONE:"})

        return self._create_result(
            success=False,
            error="Máximo de iterações atingido",
            files_created=files_created
        )

    def _process_action(self, response: str, files_created: list, files_modified: list) -> str:
        """Processa ação da resposta"""
        import requests

        # FILE - Criar arquivo
        file_match = re.search(r'```file:([^\n]+)\n(.*?)```', response, re.DOTALL)
        if file_match:
            filepath = file_match.group(1).strip()
            content = file_match.group(2)
            result = self._create_file(filepath, content)
            files_created.append(filepath)
            return result

        # BROWSER - Abrir URL (para mostrar HTML)
        browser_match = re.search(r'```browser\s*(.*?)```', response, re.DOTALL)
        if browser_match:
            cmd_json = browser_match.group(1).strip()
            try:
                cmd = json.loads(cmd_json)
                resp = requests.post("http://localhost:8888", json=cmd, timeout=30)
                return json.dumps(resp.json(), indent=2, ensure_ascii=False)
            except Exception as e:
                return f"ERRO browser: {str(e)}"

        # SHELL - Executar comando
        shell_match = re.search(r'```shell\s*(.*?)```', response, re.DOTALL)
        if shell_match:
            command = shell_match.group(1).strip()
            return self._execute_shell(command)

        # PYTHON - Executar inline
        python_match = re.search(r'```python\s*(.*?)```', response, re.DOTALL)
        if python_match:
            code = python_match.group(1).strip()
            return self._execute_python(code)

        return None

    def _create_file(self, filepath: str, content: str) -> str:
        """Cria arquivo no container"""
        working_dir = self.executor.working_dir

        if filepath.startswith("./"):
            full_path = f"{working_dir}/{filepath[2:]}"
        else:
            full_path = f"{working_dir}/{filepath}"

        # Cria diretório
        dir_path = "/".join(full_path.split("/")[:-1])
        self.executor.execute_shell(f"mkdir -p {dir_path}")

        # Cria arquivo via base64
        encoded = base64.b64encode(content.encode()).decode()
        command = f"echo '{encoded}' | base64 -d > {full_path}"

        result = subprocess.run(
            ["docker", "exec", self.executor.container, "bash", "-c", command],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            return f"✅ Arquivo criado: {filepath}"
        return f"ERRO: {result.stderr}"

    def _execute_shell(self, command: str) -> str:
        """Executa comando shell"""
        return self.executor.execute_shell(command)

    def _execute_python(self, code: str) -> str:
        """Executa código Python inline"""
        escaped = code.replace("'", "'\\''")
        command = f"DISPLAY=:1 /opt/venv/bin/python3 -c '{escaped}'"
        return self.executor.execute_shell(command)
