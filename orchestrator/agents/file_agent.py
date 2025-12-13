"""
FileAgent - Especializado em gerenciamento de arquivos
"""

import re
import json
import base64
import subprocess
from .base import BaseAgent, Task, TaskResult

FILE_AGENT_PROMPT = """Você é um agente especializado em gerenciamento de arquivos.

<capacidades>
- Criar, ler, modificar e deletar arquivos
- Organizar estrutura de pastas
- Mover e copiar arquivos
- Listar conteúdo de diretórios
- Processar arquivos de texto
- Compactar e descompactar
</capacidades>

<estrutura_projeto>
./src/      - Scripts
./web/      - HTML, CSS, JS
./data/     - Dados
./output/   - Resultados
</estrutura_projeto>

<comandos>
1. Listar arquivos:
```shell
ls -la ./src/
```

2. Criar arquivo:
```file:./data/config.json
{{"key": "value"}}
```

3. Ler arquivo:
```shell
cat ./data/config.json
```

4. Mover/Copiar:
```shell
cp ./data/file.txt ./output/
mv ./temp.txt ./data/
```

5. Criar pasta:
```shell
mkdir -p ./data/subpasta
```
</comandos>

<tarefa>
{task_description}
</tarefa>

<contexto>
{context}
</contexto>

<estrutura_atual>
{current_structure}
</estrutura_atual>

Execute operações de arquivo. Ao terminar: DONE: <resumo>
"""


class FileAgent(BaseAgent):
    """Agente especializado em arquivos"""

    def __init__(self, llm_client, executor):
        super().__init__("FileAgent", llm_client, executor)
        self.capabilities = [
            "file_management",
            "directory_operations",
            "file_processing",
            "organization"
        ]

    def can_handle(self, task_description: str) -> bool:
        """Verifica se pode lidar com a tarefa"""
        keywords = [
            "arquivo", "pasta", "diretório", "criar", "mover", "copiar",
            "deletar", "listar", "organizar", "renomear", "ler",
            "salvar", "zip", "compactar"
        ]
        task_lower = task_description.lower()
        return any(kw in task_lower for kw in keywords)

    def execute(self, task: Task) -> TaskResult:
        """Executa tarefa de arquivos"""

        context = task.context.get("memory", "")
        structure = self._get_project_structure()

        messages = [
            {"role": "system", "content": FILE_AGENT_PROMPT.format(
                task_description=task.description,
                context=context,
                current_structure=structure
            )}
        ]

        max_iterations = 10
        files_created = []
        files_modified = []

        for i in range(max_iterations):
            response = self._call_llm(messages)
            messages.append({"role": "assistant", "content": response})

            if "DONE:" in response:
                summary = response.split("DONE:")[-1].strip()
                return self._create_result(
                    success=True,
                    message=summary,
                    files_created=files_created,
                    files_modified=files_modified
                )

            result = self._process_action(response, files_created, files_modified)

            if result:
                messages.append({"role": "user", "content": f"Resultado:\n{result}\n\nContinue ou DONE:"})
            else:
                messages.append({"role": "user", "content": "Execute uma ação ou DONE:"})

        return self._create_result(
            success=False,
            error="Máximo de iterações",
            files_created=files_created
        )

    def _get_project_structure(self) -> str:
        """Obtém estrutura do projeto"""
        result = self.executor.execute_shell("find . -type f | head -30")
        return result if result.strip() else "Projeto vazio"

    def _process_action(self, response: str, files_created: list, files_modified: list) -> str:
        """Processa ação"""

        # FILE - Criar arquivo
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
            cmd = shell_match.group(1).strip()

            # Detecta operações de arquivo para tracking
            if cmd.startswith("cp ") or cmd.startswith("mv "):
                parts = cmd.split()
                if len(parts) >= 3:
                    files_modified.append(parts[-1])

            return self.executor.execute_shell(cmd)

        return None

    def _create_file(self, filepath: str, content: str) -> str:
        """Cria arquivo"""
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

    def list_files(self, path: str = ".") -> str:
        """Lista arquivos em um diretório"""
        return self.executor.execute_shell(f"ls -la {path}")

    def read_file(self, filepath: str) -> str:
        """Lê conteúdo de arquivo"""
        return self.executor.execute_shell(f"cat {filepath}")
