"""
CLI do Agente com Gerenciamento de Projetos
"""

import re
from agent import Agent
from llm_client import create_client
from project_manager import ProjectManager, format_project_list


def print_header():
    """Imprime cabeçalho"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║              AGENTE AUTÔNOMO - GERENCIADOR DE PROJETOS       ║
╠══════════════════════════════════════════════════════════════╣
║  Comandos:                                                   ║
║    NEW_PROJECT <nome>  - Criar novo projeto                  ║
║    SELECT_PROJECT      - Listar projetos                     ║
║    SELECT_<id>         - Selecionar projeto (ex: SELECT_1)   ║
║    DELETE_<id>         - Deletar projeto                     ║
║    INFO                - Info do projeto atual               ║
║    sair                - Encerrar                            ║
╚══════════════════════════════════════════════════════════════╝
    """)


def print_project_status(pm: ProjectManager):
    """Mostra status do projeto atual"""
    project = pm.get_current_project()
    if project:
        print(f"\n📁 Projeto Ativo: [{project['id']}] {project['name']}")
        print(f"   Diretório: {project['path']}")
    else:
        print("\n⚠️  Nenhum projeto selecionado")


def handle_command(cmd: str, pm: ProjectManager) -> tuple[bool, str]:
    """
    Processa comandos de gerenciamento de projeto.
    Retorna (handled: bool, message: str)
    """
    cmd_upper = cmd.strip().upper()

    # NEW_PROJECT <nome>
    if cmd_upper.startswith("NEW_PROJECT"):
        parts = cmd.split(maxsplit=1)
        if len(parts) < 2:
            return True, "Uso: NEW_PROJECT <nome do projeto>"

        name = parts[1].strip()
        desc = input("Descrição (opcional): ").strip()

        project = pm.create_project(name, desc)
        return True, f"""
✅ Projeto criado com sucesso!
   ID: {project['id']}
   Nome: {project['name']}
   Diretório: {project['path']}

Projeto selecionado automaticamente. Digite sua tarefa.
"""

    # SELECT_PROJECT - lista projetos
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
            return True, f"""
✅ Projeto selecionado: [{project['id']}] {project['name']}
   Diretório: {project['path']}

Digite sua tarefa.
"""
        else:
            return True, f"❌ Projeto #{project_id} não encontrado. Use SELECT_PROJECT para ver a lista."

    # DELETE_<id>
    match = re.match(r"DELETE_(\d+)", cmd_upper)
    if match:
        project_id = int(match.group(1))
        confirm = input(f"Tem certeza que deseja deletar o projeto #{project_id}? (s/N): ")
        if confirm.lower() == 's':
            if pm.delete_project(project_id):
                return True, f"✅ Projeto #{project_id} movido para lixeira."
            else:
                return True, f"❌ Projeto #{project_id} não encontrado."
        return True, "Cancelado."

    # INFO
    if cmd_upper == "INFO":
        project = pm.get_current_project()
        if project:
            files = pm.get_project_files()
            return True, f"""
╔══════════════════════════════════════════════════════════════╗
║                    INFORMAÇÕES DO PROJETO                    ║
╠══════════════════════════════════════════════════════════════╣
   ID: {project['id']}
   Nome: {project['name']}
   Descrição: {project.get('description', 'N/A')}
   Status: {project.get('status', 'active')}
   Criado em: {project.get('created_at', 'N/A')}
   Diretório: {project['path']}

   Arquivos:
{files}
╚══════════════════════════════════════════════════════════════╝
"""
        return True, "⚠️  Nenhum projeto selecionado."

    # Não é um comando de projeto
    return False, ""


def interativo():
    """Modo interativo com gerenciamento de projetos"""

    print_header()

    # Inicializa
    pm = ProjectManager()
    llm = create_client()
    agent = Agent(llm)

    # Compartilha o project_manager com o agent
    agent.project_manager = pm

    print_project_status(pm)

    while True:
        try:
            # Mostra prompt contextual
            project = pm.get_current_project()
            if project:
                prompt = f"\n[{project['id']}:{project['name'][:20]}] > "
            else:
                prompt = "\n[sem projeto] > "

            task = input(prompt).strip()

            if not task:
                continue

            if task.lower() in ["sair", "exit", "quit"]:
                print("👋 Até mais!")
                break

            # Tenta processar como comando de projeto
            handled, message = handle_command(task, pm)
            if handled:
                print(message)
                continue

            # Verifica se tem projeto selecionado para executar tarefas
            if not pm.get_current_project():
                print("\n⚠️  Selecione ou crie um projeto primeiro!")
                print("   Use: NEW_PROJECT <nome> ou SELECT_<id>")
                continue

            # Executa tarefa no agente
            result = agent.run(task)
            print(f"\n{'─'*60}")
            print(f"📋 RESULTADO: {result}")
            print(f"{'─'*60}")

        except KeyboardInterrupt:
            print("\n\n👋 Interrompido. Até mais!")
            break
        except Exception as e:
            print(f"\n❌ Erro: {str(e)}")


if __name__ == "__main__":
    interativo()
