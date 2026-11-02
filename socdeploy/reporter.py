"""Génération et affichage des rapports de déploiement."""

from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from jinja2 import Environment, FileSystemLoader
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from loguru import logger
from socdeploy.models import UserConfig, ServiceState
from socdeploy.system import system


class DeploymentReporter:
    """Générateur de rapport Markdown et affichage terminal Rich."""

    def __init__(self, templates_dir: Path = Path("templates")):
        self.templates_dir = templates_dir
        self.console = Console(legacy_windows=False)

    def generate_markdown(
        self,
        config: UserConfig,
        services: List[ServiceState],
        output_path: Path,
        integrations: Optional[Dict[str, Any]] = None
    ) -> Path:
        """Génère le rapport markdown et le sauvegarde."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        context = {
            "config": config,
            "services": services,
            "integrations": integrations or {},
            "date": date_str,
            "system": system.to_dict(),
        }

        template_file = self.templates_dir / "report.md.j2"
        if template_file.exists():
            env = Environment(loader=FileSystemLoader(str(self.templates_dir)))
            template = env.get_template("report.md.j2")
            content = template.render(**context)
        else:
            content = f"# Rapport de déploiement — {config.stack_name}\n\n"
            content += f"Généré le {date_str}\n\n"
            for s in services:
                content += f"- **{s.plugin}** ({s.mode}) : {s.status} — URLs: {', '.join(s.urls)}\n"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"Rapport sauvegardé : {output_path}")
        return output_path

    def print_summary(self, config: UserConfig, services: List[ServiceState], report_path: Path) -> None:
        """Affiche un résumé soigné dans le terminal avec Rich."""
        self.console.print()
        self.console.print(
            Panel.fit(
                f"[bold green]✨ Déploiement de la stack '{config.stack_name}' terminé ![/bold green]\n"
                f"Rapport complet généré dans : [cyan]{report_path}[/cyan]",
                title="SOC Deploy Framework",
                border_style="green"
            )
        )

        table = Table(title="Services SOC Déployés", show_header=True, header_style="bold magenta")
        table.add_column("Outil", style="bold")
        table.add_column("Mode", style="cyan")
        table.add_column("Méthode", style="yellow")
        table.add_column("Statut", justify="center")
        table.add_column("Accès / URLs")
        table.add_column("Identifiants")

        for svc in services:
            status_str = "[green]✔ Actif[/green]" if svc.status == "installed" else "[red]✖ Échec[/red]"
            urls_str = "\n".join(svc.urls) if svc.urls else "-"

            creds_list = []
            if svc.credentials:
                if "username" in svc.credentials:
                    creds_list.append(f"user: {svc.credentials['username']}")
                if "password" in svc.credentials:
                    creds_list.append(f"pass: {svc.credentials['password']}")
            creds_str = "\n".join(creds_list) if creds_list else "-"

            table.add_row(
                svc.plugin,
                svc.mode,
                svc.method,
                status_str,
                urls_str,
                creds_str
            )

        self.console.print(table)
        self.console.print()
