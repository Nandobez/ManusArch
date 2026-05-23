"""
Main - CLI com sistema multi-agente
Arquitetura similar ao Manus
"""

import re
from agent import SandboxExecutor, Agent
from llm_client import create_client
from project_manager import ProjectManager, format_project_list
from agents import Coordinator, WebAgent, CodeAgent, DataAgent, FileAgent


def print_header():
    """Imprime cabeçalho"""
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    🤖 MULTI-AGENT SYSTEM (Manus-like)                        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Agentes:                                                                    ║
║    🌐 WebAgent   - Navegação, scraping, extração de dados web                ║
║    💻 CodeAgent  - Criação e execução de código Python                       ║
║    📊 DataAgent  - Análise de dados, APIs, visualizações                     ║
║    📁 FileAgent  - Gerenciamento de arquivos e diretórios                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Comandos:                                                                   ║
║    NEW_PROJECT <nome>   - Criar projeto                                      ║
║    SELECT_PROJECT       - Listar projetos                                    ║
║    SELECT_<id>          - Selecionar projeto                                 ║
║    INFO                 - Info do projeto                                    ║
║    TURBO                - Modo rápido (agente único, sem decomposição)       ║
║    MULTI                - Modo multi-agente (padrão)                         ║
║    sair                 - Encerrar                                           ║
╚══════════════════════════════════════════════════════════════════════════════╝
    """)


def handle_command(cmd: str, pm: ProjectManager, coordinator: Coordinator) -> tuple[bool, str]:
    """Processa comandos do sistema"""
    cmd_upper = cmd.strip().upper()

    # NEW_PROJECT
    if cmd_upper.startswith("NEW_PROJECT"):
        parts = cmd.split(maxsplit=1)
        if len(parts) < 2:
            return True, "Uso: NEW_PROJECT <nome>"

        name = parts[1].strip()
        desc = input("Descrição (opcional): ").strip()
        project = pm.create_project(name, desc)
        coordinator.clear_memory()  # Limpa memória ao criar novo projeto

        return True, f"""
✅ Projeto criado: [{project['id']}] {project['name']}
   Diretório: {project['path']}

Projeto selecionado. Digite sua tarefa.
"""

    # SELECT_PROJECT
    if cmd_upper == "SELECT_PROJECT":
        projects = pm.list_projects()
        current = pm.get_current_project()
        current_id = current["id"] if current else None
        return True, format_project_list(projects, current_id)

    # SELECT_<id>
    match = re.match(r"SELECT_(\d+)", cmd_upper)
    if match:
        project_id = int(match.group(1))
        project = pm.select_project(project_id)
        if project:
            coordinator.clear_memory()  # Limpa memória ao trocar de projeto
            return True, f"""
✅ Projeto selecionado: [{project['id']}] {project['name']}
   Diretório: {project['path']}

Memória limpa. Digite sua tarefa.
"""
        return True, f"❌ Projeto #{project_id} não encontrado."

    # DELETE_<id>
    match = re.match(r"DELETE_(\d+)", cmd_upper)
    if match:
        project_id = int(match.group(1))
        confirm = input(f"Deletar projeto #{project_id}? (s/N): ")
        if confirm.lower() == 's':
            if pm.delete_project(project_id):
                return True, f"✅ Projeto #{project_id} deletado."
            return True, f"❌ Projeto não encontrado."
        return True, "Cancelado."

    # INFO
    if cmd_upper == "INFO":
        project = pm.get_current_project()
        if project:
            files = pm.get_project_files()
            return True, f"""
╔═══════════════════════════════════════════════════════════════╗
║                    PROJETO: {project['name'][:30]:<30} ║
╠═══════════════════════════════════════════════════════════════╣
   ID: {project['id']}
   Descrição: {project.get('description', 'N/A')}
   Status: {project.get('status', 'active')}
   Diretório: {project['path']}

   Arquivos:
{files}
╚═══════════════════════════════════════════════════════════════╝
"""
        return True, "⚠️ Nenhum projeto selecionado."

    # MEMORY
    if cmd_upper == "MEMORY":
        memory = coordinator.get_memory()
        return True, f"""
╔═══════════════════════════════════════════════════════════════╗
║                    MEMÓRIA COMPARTILHADA                       ║
╠═══════════════════════════════════════════════════════════════╣
{memory.get_context_summary()}

Tarefas completadas: {len(coordinator.completed_tasks)}
╚═══════════════════════════════════════════════════════════════╝
"""

    # CLEAR_MEMORY
    if cmd_upper == "CLEAR_MEMORY":
        coordinator.clear_memory()
        return True, "✅ Memória limpa."

    return False, ""


def main():
    """Loop principal"""

    print_header()

    # Inicializa componentes
    print("Inicializando sistema...")
    pm = ProjectManager()
    llm = create_client()
    executor = SandboxExecutor()

    # Cria coordenador multi-agente
    coordinator = Coordinator(llm, executor, pm)

    # Registra agentes especializados
    print("Registrando agentes:")
    coordinator.register_agent(WebAgent(llm, executor))
    coordinator.register_agent(CodeAgent(llm, executor))
    coordinator.register_agent(DataAgent(llm, executor))
    coordinator.register_agent(FileAgent(llm, executor))

    # Cria agente único para modo turbo
    single_agent = Agent(llm)
    single_agent.project_manager = pm

    # Modo de operação (TURBO é padrão - mais rápido)
    turbo_mode = True

    print("\n✓ Sistema pronto!")
    print("⚡ Modo TURBO ativado (digite MULTI para multi-agente)\n")

    # Status inicial
    project = pm.get_current_project()
    if project:
        print(f"📁 Projeto ativo: [{project['id']}] {project['name']}")
    else:
        print("⚠️ Nenhum projeto selecionado. Use NEW_PROJECT ou SELECT_<id>")

    # Loop principal
    while True:
        try:
            # Prompt contextual
            project = pm.get_current_project()
            mode_icon = "⚡" if turbo_mode else "🤖"
            if project:
                prompt = f"\n[{project['id']}:{project['name'][:15]}] {mode_icon} > "
            else:
                prompt = f"\n[sem projeto] {mode_icon} > "

            task = input(prompt).strip()

            if not task:
                continue

            if task.lower() in ["sair", "exit", "quit"]:
                print("👋 Até mais!")
                break

            # Comandos de modo
            if task.upper() == "TURBO":
                turbo_mode = True
                print("⚡ Modo TURBO ativado (agente único, mais rápido)")
                continue
            if task.upper() == "MULTI":
                turbo_mode = False
                print("🤖 Modo MULTI-AGENTE ativado")
                continue

            # Processa comandos do sistema
            handled, message = handle_command(task, pm, coordinator)
            if handled:
                print(message)
                continue

            # Verifica projeto
            if not pm.get_current_project():
                print("\n⚠️ Crie ou selecione um projeto primeiro!")
                continue

            # Atualiza diretório de trabalho
            executor.set_working_dir(pm.get_project_path())

            # Executa tarefa
            if turbo_mode:
                # Modo turbo: agente único
                print(f"\n⚡ Executando em modo TURBO...")
                result_msg = single_agent.run(task)
                print(f"\n{'─'*70}")
                print(f"📋 RESULTADO: {result_msg}")
                print(f"{'─'*70}")
                continue

            # Modo multi-agente
            result = coordinator.run(task)

            # Exibe resultado
            print(f"\n{'─'*70}")
            print(f"📋 RESULTADO FINAL:")
            print(f"   Tarefas: {result['completed']}/{result['total_tasks']} completadas")

            if result['files_created']:
                print(f"   Arquivos criados: {', '.join(result['files_created'][:5])}")

            if result['errors']:
                print(f"   ⚠️ Erros: {len(result['errors'])}")
                for err in result['errors'][:3]:
                    print(f"      - {err[:60]}")

            print(f"{'─'*70}")

        except KeyboardInterrupt:
            print("\n\n👋 Interrompido.")
            break
        except Exception as e:
            print(f"\n❌ Erro: {str(e)}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    main()
