"""
Gerenciador de Projetos - Cada projeto é uma pasta isolada no container
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

CONTAINER_NAME = "sandbox"
PROJECTS_BASE = "/workspace/projects"
PROJECTS_META = "/workspace/projects/.projects.json"


class ProjectManager:
    """Gerencia projetos dentro do container"""

    def __init__(self, container_name: str = CONTAINER_NAME):
        self.container = container_name
        self.current_project: Optional[dict] = None
        self._ensure_projects_dir()

    def _exec(self, command: str) -> str:
        """Executa comando no container"""
        try:
            result = subprocess.run(
                ["docker", "exec", self.container, "bash", "-c", command],
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.stdout + result.stderr
        except Exception as e:
            return f"ERRO: {str(e)}"

    def _ensure_projects_dir(self):
        """Garante que a pasta de projetos existe"""
        self._exec(f"mkdir -p {PROJECTS_BASE}")
        # Cria arquivo de metadados se não existir
        self._exec(f"[ -f {PROJECTS_META} ] || echo '[]' > {PROJECTS_META}")

    def _load_projects(self) -> list:
        """Carrega lista de projetos"""
        output = self._exec(f"cat {PROJECTS_META}")
        try:
            return json.loads(output.strip())
        except:
            return []

    def _save_projects(self, projects: list):
        """Salva lista de projetos"""
        json_str = json.dumps(projects, indent=2, ensure_ascii=False)
        # Escapa para bash
        escaped = json_str.replace("'", "'\\''")
        self._exec(f"echo '{escaped}' > {PROJECTS_META}")

    def create_project(self, name: str, description: str = "") -> dict:
        """Cria um novo projeto"""
        projects = self._load_projects()

        # Gera ID incremental
        max_id = max([p.get("id", 0) for p in projects], default=0)
        new_id = max_id + 1

        # Cria pasta do projeto
        folder_name = f"{new_id:03d}_{self._sanitize_name(name)}"
        project_path = f"{PROJECTS_BASE}/{folder_name}"

        self._exec(f"mkdir -p {project_path}")

        # Cria estrutura básica
        self._exec(f"mkdir -p {project_path}/src")
        self._exec(f"mkdir -p {project_path}/web")
        self._exec(f"mkdir -p {project_path}/data")
        self._exec(f"mkdir -p {project_path}/output")

        # Cria arquivo de info do projeto
        project = {
            "id": new_id,
            "name": name,
            "description": description,
            "folder": folder_name,
            "path": project_path,
            "created_at": datetime.now().isoformat(),
            "status": "active"
        }

        # Cria README no projeto
        readme = f"# {name}\n\n{description}\n\nCriado em: {project['created_at']}\n"
        self._exec(f"echo '{readme}' > {project_path}/README.md")

        # Salva na lista
        projects.append(project)
        self._save_projects(projects)

        # Seleciona automaticamente o novo projeto
        self.current_project = project

        return project

    def list_projects(self) -> list:
        """Lista todos os projetos"""
        return self._load_projects()

    def select_project(self, project_id: int) -> Optional[dict]:
        """Seleciona um projeto pelo ID"""
        projects = self._load_projects()

        for p in projects:
            if p["id"] == project_id:
                self.current_project = p
                return p

        return None

    def get_current_project(self) -> Optional[dict]:
        """Retorna o projeto atual"""
        return self.current_project

    def get_project_path(self) -> str:
        """Retorna o caminho do projeto atual"""
        if self.current_project:
            return self.current_project["path"]
        return PROJECTS_BASE

    def delete_project(self, project_id: int) -> bool:
        """Deleta um projeto (move para .trash)"""
        projects = self._load_projects()

        for i, p in enumerate(projects):
            if p["id"] == project_id:
                # Move para trash ao invés de deletar
                self._exec(f"mkdir -p {PROJECTS_BASE}/.trash")
                self._exec(f"mv {p['path']} {PROJECTS_BASE}/.trash/")

                # Remove da lista
                projects.pop(i)
                self._save_projects(projects)

                # Limpa seleção se era o projeto atual
                if self.current_project and self.current_project["id"] == project_id:
                    self.current_project = None

                return True

        return False

    def _sanitize_name(self, name: str) -> str:
        """Sanitiza nome para usar como pasta"""
        # Remove caracteres especiais, substitui espaços por underscore
        import re
        sanitized = re.sub(r'[^\w\s-]', '', name)
        sanitized = re.sub(r'[\s]+', '_', sanitized)
        return sanitized[:50].lower()

    def archive_project(self, project_id: int) -> bool:
        """Arquiva um projeto"""
        projects = self._load_projects()

        for p in projects:
            if p["id"] == project_id:
                p["status"] = "archived"
                self._save_projects(projects)
                return True

        return False

    def get_project_files(self) -> str:
        """Lista arquivos do projeto atual"""
        if not self.current_project:
            return "Nenhum projeto selecionado"

        return self._exec(f"find {self.current_project['path']} -type f | head -50")


def format_project_list(projects: list, current_id: Optional[int] = None) -> str:
    """Formata lista de projetos para exibição"""
    if not projects:
        return "Nenhum projeto encontrado. Use NEW_PROJECT para criar um."

    lines = ["\n╔══════════════════════════════════════════════════════════════╗"]
    lines.append("║                     PROJETOS DISPONÍVEIS                      ║")
    lines.append("╠══════════════════════════════════════════════════════════════╣")

    for p in projects:
        marker = "►" if current_id and p["id"] == current_id else " "
        status = "📁" if p.get("status") == "active" else "📦"
        line = f"║ {marker} [{p['id']:3d}] {status} {p['name'][:40]:<40} ║"
        lines.append(line)

    lines.append("╚══════════════════════════════════════════════════════════════╝")
    lines.append("\nComandos: SELECT_<id> para selecionar | NEW_PROJECT para criar")

    return "\n".join(lines)
