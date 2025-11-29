"""
WebAgent - Especializado em navegação web e extração de dados
"""

import json
import re
import requests
from .base import BaseAgent, Task, TaskResult

WEB_AGENT_PROMPT = """Você é um agente especializado em navegação web e extração de dados.

<capacidades>
- Navegar para URLs
- Extrair texto e dados de páginas
- Clicar em elementos
- Preencher formulários
- Tirar screenshots
- Fazer scroll em páginas
</capacidades>

<comandos_browser>
Para controlar o browser, responda com um bloco ```browser contendo JSON:

Navegar: {{"action": "goto", "params": {{"url": "https://..."}}}}
Clicar: {{"action": "click", "params": {{"selector": "button#id"}}}}
Digitar: {{"action": "type", "params": {{"selector": "input#search", "text": "..."}}}}
Pressionar tecla: {{"action": "press", "params": {{"key": "Enter"}}}}
Screenshot: {{"action": "screenshot", "params": {{"path": "./output/screenshot.png"}}}}
Extrair texto: {{"action": "get_text", "params": {{"selector": "body"}}}}
Extrair múltiplos: {{"action": "get_all_text", "params": {{"selector": ".class"}}}}
Scroll: {{"action": "scroll", "params": {{"direction": "down", "amount": 500}}}}
Esperar: {{"action": "wait", "params": {{"ms": 2000}}}}
Esperar elemento: {{"action": "wait_for", "params": {{"selector": "#element", "timeout": 10000}}}}
Executar JS: {{"action": "eval", "params": {{"script": "document.title"}}}}
</comandos_browser>

<seletores_youtube>
IMPORTANTE - Seletores que funcionam no YouTube:
- Barra de busca: input#search, input[name="search_query"]
- Botão buscar: button#search-icon-legacy
- Título de vídeo: #video-title, ytd-video-renderer #video-title
- Lista de resultados: ytd-video-renderer
- Player de vídeo: #movie_player
</seletores_youtube>

<comandos_youtube_especiais>
Para coletar comentários do YouTube, use ESTES comandos na ordem:

1. Primeiro faça scroll para carregar comentários:
{{"action": "scroll_to_comments"}}

2. Depois extraia os comentários:
{{"action": "get_youtube_comments", "params": {{"count": 5}}}}

Isso retornará uma lista com autor e texto de cada comentário.
NÃO use get_text para comentários - use get_youtube_comments!
</comandos_youtube_especiais>

<tarefa>
{task_description}
</tarefa>

<contexto>
{context}
</contexto>

Execute a tarefa passo a passo. Responda com UM comando por vez.

⚠️ REGRAS CRÍTICAS:
- NÃO diga DONE até ter EXTRAÍDO os dados solicitados
- Para comentários do YouTube: use scroll_to_comments + get_youtube_comments
- Só finalize com DONE: quando tiver os DADOS REAIS extraídos
- Se a tarefa pede comentários, você DEVE retornar os textos dos comentários

Após executar TODOS os passos e ter os dados, finalize com: DONE: <resumo incluindo os dados extraídos>
"""


class WebAgent(BaseAgent):
    """Agente especializado em navegação web"""

    def __init__(self, llm_client, executor, browser_url: str = "http://localhost:8888"):
        super().__init__("WebAgent", llm_client, executor)
        self.browser_url = browser_url
        self.capabilities = [
            "browsing",
            "web_scraping",
            "form_filling",
            "screenshot",
            "data_extraction"
        ]

    def can_handle(self, task_description: str) -> bool:
        """Verifica se pode lidar com a tarefa"""
        keywords = [
            "navegar", "acessar", "abrir", "site", "página", "web",
            "browser", "firefox", "screenshot", "extrair", "scraping",
            "url", "http", "link", "clicar", "formulário"
        ]
        task_lower = task_description.lower()
        return any(kw in task_lower for kw in keywords)

    def execute(self, task: Task) -> TaskResult:
        """Executa tarefa de navegação web"""

        context = task.context.get("memory", "")
        messages = [
            {"role": "system", "content": WEB_AGENT_PROMPT.format(
                task_description=task.description,
                context=context
            )}
        ]

        max_iterations = 35  # Mais iterações para tarefas complexas no YouTube
        files_created = []
        extracted_data = []  # Dados extraídos para passar ao próximo agente

        for i in range(max_iterations):
            response = self._call_llm(messages)
            messages.append({"role": "assistant", "content": response})

            # Verifica se terminou
            if "DONE:" in response:
                summary = response.split("DONE:")[-1].strip()
                result = self._create_result(
                    success=True,
                    message=summary,
                    files_created=files_created,
                    data={"extracted": extracted_data} if extracted_data else {}
                )
                return result

            # Extrai comando de browser
            browser_match = re.search(r'```browser\s*(.*?)```', response, re.DOTALL)
            if browser_match:
                cmd_json = browser_match.group(1).strip()
                result = self._execute_browser_command(cmd_json)

                # Rastreia screenshots e dados extraídos
                try:
                    cmd = json.loads(cmd_json)
                    if cmd.get("action") == "screenshot":
                        files_created.append(cmd.get("params", {}).get("path", ""))

                    # Salva dados extraídos
                    result_dict = json.loads(result)
                    if result_dict.get("success"):
                        if "text" in result_dict:
                            extracted_data.append({"type": "text", "content": result_dict["text"]})
                        if "texts" in result_dict:
                            extracted_data.append({"type": "texts", "content": result_dict["texts"]})
                except:
                    pass

                messages.append({"role": "user", "content": f"Resultado:\n{result}\n\nContinue ou finalize com DONE:"})
            else:
                messages.append({"role": "user", "content": "Execute um comando ```browser ou finalize com DONE:"})

        return self._create_result(
            success=False,
            error="Máximo de iterações atingido",
            files_created=files_created
        )

    def _execute_browser_command(self, cmd_json: str) -> str:
        """Executa comando no browser server"""
        try:
            cmd = json.loads(cmd_json)

            # Ajusta caminhos relativos
            working_dir = self.executor.working_dir
            if cmd.get("action") == "screenshot":
                path = cmd.get("params", {}).get("path", "")
                if path.startswith("./"):
                    cmd["params"]["path"] = f"{working_dir}/{path[2:]}"

            response = requests.post(self.browser_url, json=cmd, timeout=30)
            return json.dumps(response.json(), indent=2, ensure_ascii=False)
        except Exception as e:
            return f"ERRO: {str(e)}"
