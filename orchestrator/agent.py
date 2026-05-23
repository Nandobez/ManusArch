"""
Orquestrador do Agente - Controla o sandbox via Docker
"""

import subprocess
import json
import re
import requests
from pathlib import Path
from llm_client import LLMClient
from project_manager import ProjectManager, format_project_list

CONTAINER_NAME = "sandbox"
BROWSER_SERVER_URL = "http://localhost:8888"
MAX_ITERATIONS = 50  # Aumentado para tarefas complexas

SYSTEM_PROMPT_TEMPLATE = """Você é um agente que executa tarefas PASSO A PASSO. Você NÃO PODE pular etapas.

<REGRA_CRÍTICA>
⚠️ EXECUTE APENAS UMA AÇÃO POR MENSAGEM
⚠️ AGUARDE O RESULTADO ANTES DE CONTINUAR
⚠️ NUNCA INVENTE DADOS - USE APENAS DADOS QUE VOCÊ COLETOU
⚠️ NÃO DIGA "TAREFA_COMPLETA" ATÉ EXECUTAR TODOS OS PASSOS
</REGRA_CRÍTICA>

<projeto_atual>
{project_info}
</projeto_atual>

<estrutura>
./src/    - Scripts Python
./web/    - HTML, CSS, JS
./data/   - Dados coletados
./output/ - Screenshots, resultados
</estrutura>

<ferramentas>

BROWSER - Controlar Firefox (fica aberto entre comandos):
```browser
{{"action": "goto", "params": {{"url": "https://youtube.com"}}}}
```
Ações básicas: goto, click, type, press, screenshot, get_text, scroll, wait

⚠️ Para comentários do YOUTUBE especificamente:
1. Primeiro: {{"action": "scroll_to_comments"}}
2. Depois: {{"action": "get_youtube_comments", "params": {{"count": 5}}}}
Isso retorna lista de {{author, text}} - USE ESSES COMANDOS!

FILE - Criar arquivo:
```file:./caminho/arquivo.ext
conteúdo
```

SHELL - Executar comando:
```shell
python3 ./src/script.py
```

PYTHON - Código rápido:
```python
print("teste")
```
</ferramentas>

<FLUXO_OBRIGATÓRIO>
1. ANALISE a tarefa e identifique os passos
2. EXECUTE UM passo (uma única ação)
3. PARE e aguarde o resultado
4. ANALISE o resultado recebido
5. EXECUTE o próximo passo baseado no resultado REAL
6. REPITA até completar TODOS os passos
7. SÓ ENTÃO diga TAREFA_COMPLETA
</FLUXO_OBRIGATÓRIO>

<exemplo_CORRETO>
Tarefa: Abra YouTube e pegue o título do primeiro vídeo

Resposta 1:
Vou abrir o YouTube primeiro.
```browser
{{"action": "goto", "params": {{"url": "https://youtube.com"}}}}
```

[Sistema retorna: success, title: YouTube]

Resposta 2:
YouTube aberto. Agora vou aguardar carregar.
```browser
{{"action": "wait", "params": {{"ms": 2000}}}}
```

[Sistema retorna: success]

Resposta 3:
Agora vou extrair o título do primeiro vídeo.
```browser
{{"action": "get_text", "params": {{"selector": "#video-title"}}}}
```

[Sistema retorna: "Vídeo ABC - Canal XYZ"]

Resposta 4:
TAREFA_COMPLETA: O título do primeiro vídeo é "Vídeo ABC - Canal XYZ"
</exemplo_CORRETO>

<exemplo_ERRADO>
❌ PROIBIDO - Criar HTML com dados inventados:
```file:./web/index.html
<p>Comentário 1</p>  ← DADO INVENTADO!
<p>Comentário 2</p>  ← VOCÊ NÃO COLETOU ISSO!
```
TAREFA_COMPLETA

Isso é ERRADO! Primeiro colete os dados REAIS, depois crie o arquivo.
</exemplo_ERRADO>

Execute PASSO A PASSO. UMA ação por mensagem. Aguarde resultados.
"""


class SandboxExecutor:
    """Executa comandos no container Docker"""

    def __init__(self, container_name: str = CONTAINER_NAME):
        self.container = container_name
        self.browser_url = BROWSER_SERVER_URL
        self.working_dir = "/workspace"

    def set_working_dir(self, path: str):
        """Define o diretório de trabalho"""
        self.working_dir = path

    def execute_shell(self, command: str) -> str:
        """Executa comando shell no container"""
        try:
            full_command = f"cd {self.working_dir} && {command}"
            result = subprocess.run(
                ["docker", "exec", self.container, "bash", "-c", full_command],
                capture_output=True,
                text=True,
                timeout=60
            )
            output = result.stdout + result.stderr
            return output[:5000]  # Limita output
        except subprocess.TimeoutExpired:
            return "ERRO: Comando excedeu timeout de 60s"
        except Exception as e:
            return f"ERRO: {str(e)}"

    def execute_python(self, code: str) -> str:
        """Executa código Python no container"""
        # Escapa o código para passar via bash
        escaped_code = code.replace("'", "'\\''")
        command = f"DISPLAY=:1 /opt/venv/bin/python3 -c '{escaped_code}'"
        return self.execute_shell(command)

    def execute_python_file(self, code: str, filename: str = "temp_script.py") -> str:
        """Salva código em arquivo e executa (melhor para scripts complexos)"""
        # Salva o código no container
        escaped_code = code.replace("'", "'\\''")
        self.execute_shell(f"cat > {self.working_dir}/{filename} << 'EOFSCRIPT'\n{code}\nEOFSCRIPT")

        # Executa
        return self.execute_shell(f"DISPLAY=:1 /opt/venv/bin/python3 {filename}")

    def execute_browser(self, cmd_json: str) -> str:
        """Envia comando para o browser server via HTTP"""
        try:
            cmd = json.loads(cmd_json)

            # Ajusta caminhos relativos para absolutos
            if cmd.get("action") == "screenshot" and cmd.get("params", {}).get("path", "").startswith("./"):
                cmd["params"]["path"] = self.working_dir + cmd["params"]["path"][1:]

            response = requests.post(self.browser_url, json=cmd, timeout=30)
            result = response.json()
            return json.dumps(result, indent=2, ensure_ascii=False)
        except json.JSONDecodeError as e:
            return f"ERRO: JSON inválido - {str(e)}"
        except requests.exceptions.ConnectionError:
            return "ERRO: Browser server não está rodando. Verifique o container."
        except Exception as e:
            return f"ERRO: {str(e)}"

    def create_file(self, filepath: str, content: str) -> str:
        """Cria arquivo no container"""
        try:
            # Converte caminho relativo para absoluto
            if filepath.startswith("./"):
                full_path = f"{self.working_dir}/{filepath[2:]}"
            elif not filepath.startswith("/"):
                full_path = f"{self.working_dir}/{filepath}"
            else:
                full_path = filepath

            # Garante que o diretório existe
            dir_path = "/".join(full_path.split("/")[:-1])
            self.execute_shell(f"mkdir -p {dir_path}")

            # Escapa conteúdo para heredoc
            # Usa base64 para evitar problemas com caracteres especiais
            import base64
            encoded = base64.b64encode(content.encode()).decode()

            command = f"echo '{encoded}' | base64 -d > {full_path}"
            result = subprocess.run(
                ["docker", "exec", self.container, "bash", "-c", command],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                # Verifica se arquivo foi criado
                check = subprocess.run(
                    ["docker", "exec", self.container, "ls", "-la", full_path],
                    capture_output=True,
                    text=True
                )
                return f"✅ Arquivo criado: {filepath}\n{check.stdout}"
            else:
                return f"ERRO ao criar arquivo: {result.stderr}"

        except Exception as e:
            return f"ERRO: {str(e)}"


class Agent:
    """Agente autônomo que usa LLM para decidir ações"""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        self.executor = SandboxExecutor()
        self.project_manager = ProjectManager()
        self.history = []

    def _get_system_prompt(self) -> str:
        """Gera system prompt com informações do projeto atual"""
        project = self.project_manager.get_current_project()

        if project:
            project_info = f"""Nome: {project['name']}
ID: {project['id']}
Diretório: {project['path']}
Descrição: {project.get('description', 'N/A')}
Status: {project.get('status', 'active')}

Estrutura:
- ./src/ - scripts Python
- ./web/ - arquivos HTML, CSS, JS
- ./data/ - dados de entrada
- ./output/ - resultados, screenshots, exports"""
        else:
            project_info = "NENHUM PROJETO SELECIONADO - Use NEW_PROJECT ou SELECT_<id> para selecionar um projeto."

        return SYSTEM_PROMPT_TEMPLATE.format(project_info=project_info)

    def _update_working_dir(self):
        """Atualiza o diretório de trabalho do executor"""
        path = self.project_manager.get_project_path()
        self.executor.set_working_dir(path)

    def parse_action(self, response: str) -> tuple[str, str]:
        """Extrai tipo de ação e código da resposta do LLM"""

        # PRIMEIRO verifica se tem código para executar (prioridade sobre TAREFA_COMPLETA)

        # FILE - Criar arquivo (```file:./caminho/arquivo.ext)
        file_match = re.search(r'```file:([^\n]+)\n(.*?)```', response, re.DOTALL)
        if file_match:
            filepath = file_match.group(1).strip()
            content = file_match.group(2)
            return "file", json.dumps({"path": filepath, "content": content})

        if "```browser" in response:
            code = response.split("```browser")[1].split("```")[0].strip()
            return "browser", code

        if "```python" in response:
            code = response.split("```python")[1].split("```")[0].strip()
            return "python", code

        if "```shell" in response:
            code = response.split("```shell")[1].split("```")[0].strip()
            return "shell", code

        if "```bash" in response:
            code = response.split("```bash")[1].split("```")[0].strip()
            return "shell", code

        if "```json" in response and '"action"' in response:
            # Pode ser comando de browser em bloco json
            code = response.split("```json")[1].split("```")[0].strip()
            return "browser", code

        # Só verifica conclusão se NÃO tiver código
        if "TAREFA_COMPLETA:" in response:
            return "complete", response.split("TAREFA_COMPLETA:")[-1].strip()

        if "ERRO:" in response:
            return "error", response.split("ERRO:")[-1].strip()

        return "none", ""

    def run(self, task: str) -> str:
        """Executa uma tarefa usando o loop do agente"""

        # Verifica se há projeto selecionado
        project = self.project_manager.get_current_project()
        if not project:
            return "ERRO: Nenhum projeto selecionado. Use NEW_PROJECT ou SELECT_<id> primeiro."

        # Atualiza diretório de trabalho
        self._update_working_dir()

        print(f"\n{'='*60}")
        print(f"PROJETO: [{project['id']}] {project['name']}")
        print(f"TAREFA: {task}")
        print(f"{'='*60}\n")

        # Inicializa histórico com prompt dinâmico
        self.history = [
            {"role": "system", "content": self._get_system_prompt()},
            {"role": "user", "content": f"Tarefa: {task}"}
        ]

        for iteration in range(MAX_ITERATIONS):
            print(f"\n--- Iteração {iteration + 1} ---")

            # Pergunta ao LLM
            response = self.llm.chat(self.history)
            print(f"\nLLM:\n{response}\n")

            self.history.append({"role": "assistant", "content": response})

            # Parse da ação
            action_type, action_content = self.parse_action(response)

            if action_type == "complete":
                print(f"\n✓ TAREFA COMPLETA: {action_content}")
                return action_content

            if action_type == "error":
                print(f"\n✗ ERRO: {action_content}")
                return f"Erro: {action_content}"

            if action_type == "none":
                # LLM não retornou ação, pede para continuar
                self.history.append({
                    "role": "user",
                    "content": "Continue. Execute uma ação usando um bloco de código."
                })
                continue

            # Executa a ação
            print(f"Executando {action_type}...")

            if action_type == "file":
                file_data = json.loads(action_content)
                result = self.executor.create_file(file_data["path"], file_data["content"])
            elif action_type == "shell":
                result = self.executor.execute_shell(action_content)
            elif action_type == "python":
                if len(action_content) > 200 or "\n" in action_content:
                    result = self.executor.execute_python_file(action_content)
                else:
                    result = self.executor.execute_python(action_content)
            elif action_type == "browser":
                result = self.executor.execute_browser(action_content)
            else:
                result = "Tipo de ação desconhecido"

            print(f"Resultado:\n{result}\n")

            # Adiciona resultado ao histórico
            self.history.append({
                "role": "user",
                "content": f"Resultado da execução:\n```\n{result}\n```\n\nContinue com a próxima ação ou finalize a tarefa."
            })

        return "Erro: Máximo de iterações atingido"


def main():
    """Exemplo de uso"""
    from llm_client import create_client

    # Cria cliente LLM (configura em llm_client.py)
    llm = create_client()

    # Cria agente
    agent = Agent(llm)

    # Executa tarefa
    task = input("Digite a tarefa: ")
    result = agent.run(task)

    print(f"\n{'='*60}")
    print(f"RESULTADO FINAL: {result}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
