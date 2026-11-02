"""Interface en ligne de commande (CLI) de SOC Deploy Framework."""

from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from socdeploy.catalog import PluginCatalog, CATEGORY_LABELS
from socdeploy.engine import SOCDeployEngine
from socdeploy.interactive import run_interactive_wizard
from socdeploy.system import system
from socdeploy.models import UserConfig
import yaml


import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

app = typer.Typer(
    help="SOC Deploy Framework — Déploiement automatisé d'outils SOC open source.",
    no_args_is_help=False
)
console = Console(legacy_windows=False)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Point d'entrée principal. Si aucune sous-commande n'est fournie, lance le menu interactif."""
    if ctx.invoked_subcommand is None:
        console.print("[bold cyan]Lancement de l'assistant interactif SOC Deploy...[/bold cyan]")
        user_config = run_interactive_wizard()
        if not user_config:
            raise typer.Exit(code=0)

        import questionary
        proceed = questionary.confirm("Voulez-vous lancer le déploiement dès maintenant ?").ask()
        if proceed:
            config_path = Path("config.yaml")
            engine = SOCDeployEngine(config_path)
            try:
                engine.deploy()
            except Exception as e:
                console.print(f"[bold red]❌ Échec du déploiement : {e}[/bold red]")
                raise typer.Exit(code=1)


@app.command("list")
def list_plugins(
    plugins_dir: Path = typer.Option(Path("plugins"), "--plugins-dir", "-p", help="Dossier des plugins")
):
    """Affiche le catalogue de tous les outils SOC disponibles et leurs modes."""
    catalog = PluginCatalog(plugins_dir)
    plugins = catalog.list_plugins()

    if not plugins:
        console.print("[yellow]Aucun plugin trouvé.[/yellow]")
        return

    table = Table(title="🛡️ Catalogue des Outils SOC Disponibles", show_header=True, header_style="bold cyan")
    table.add_column("Identifiant", style="bold")
    table.add_column("Nom & Version")
    table.add_column("Catégorie", style="magenta")
    table.add_column("Modes disponibles", style="green")
    table.add_column("Méthodes", style="yellow")

    for p in plugins:
        cat = CATEGORY_LABELS.get(p.category, p.category)
        modes_str = ", ".join(p.modes.keys())
        all_methods = set()
        for m in p.modes.values():
            all_methods.update(m.methods.keys())
        methods_str = ", ".join(sorted(all_methods)) or "docker"

        table.add_row(
            p.name,
            f"{p.label} (v{p.version})",
            cat,
            modes_str,
            methods_str
        )

    console.print(table)
    console.print("[dim]Pour inspecter un outil en détail : [bold]socdeploy info <identifiant>[/bold][/dim]\n")


@app.command("info")
def plugin_info(
    plugin_name: str = typer.Argument(..., help="Identifiant du plugin (ex: suricata, wazuh)"),
    plugins_dir: Path = typer.Option(Path("plugins"), "--plugins-dir", "-p", help="Dossier des plugins")
):
    """Affiche la fiche détaillée d'un outil SOC (modes, variables, prérequis)."""
    catalog = PluginCatalog(plugins_dir)
    p = catalog.get_plugin(plugin_name)
    if not p:
        console.print(f"[bold red]Outil '{plugin_name}' inconnu dans le catalogue.[/bold red]")
        raise typer.Exit(code=1)

    info_text = (
        f"[bold cyan]Nom :[/bold cyan] {p.label} (v{p.version})\n"
        f"[bold cyan]Catégorie :[/bold cyan] {CATEGORY_LABELS.get(p.category, p.category)}\n"
        f"[bold cyan]Description :[/bold cyan] {p.description or 'Aucune'}\n"
        f"[bold cyan]Site officiel :[/bold cyan] {p.homepage or 'N/A'}\n\n"
        f"[bold magenta]Modes d'installation disponibles :[/bold magenta]\n"
    )

    for mode_name, mode in p.modes.items():
        info_text += f"\n  • [bold green]{mode_name}[/bold green] : {mode.description}\n"
        methods = ", ".join(mode.methods.keys())
        info_text += f"    - Méthodes : {methods}\n"
        info_text += f"    - Exigences : RAM {mode.requirements.min_ram_mb}Mo, {mode.requirements.min_cpu} CPU\n"
        if mode.requirements.ports:
            info_text += f"    - Ports requis : {mode.requirements.ports}\n"
        if mode.variables:
            info_text += f"    - Paramètres configurables : {', '.join(v.name for v in mode.variables)}\n"

    console.print(Panel(info_text, title=f"Fiche Outil : {p.name}", border_style="cyan"))


@app.command("init")
def init_config(
    output: Path = typer.Option(Path("config.yaml"), "--output", "-o", help="Chemin du fichier à générer"),
    plugins_dir: Path = typer.Option(Path("plugins"), "--plugins-dir", "-p", help="Dossier des plugins")
):
    """Lance l'assistant interactif pour générer le fichier config.yaml sans déployer."""
    user_config = run_interactive_wizard(plugins_dir=plugins_dir, output_config_path=output)
    if user_config:
        console.print(f"[bold green]✔ Fichier de configuration prêt. Pour déployer :[/bold green] socdeploy deploy -c {output}")


@app.command("deploy")
def deploy(
    config: Path = typer.Option(Path("config.yaml"), "--config", "-c", help="Fichier de configuration YAML"),
    plugins_dir: Path = typer.Option(Path("plugins"), "--plugins-dir", "-p", help="Dossier des plugins")
):
    """Déploie les outils sélectionnés dans le fichier de configuration."""
    if not config.exists():
        example = Path("config.example.yaml")
        if example.exists():
            console.print(f"[yellow]Fichier {config} introuvable. Utilisation de {example}.[/yellow]")
            config = example
        else:
            console.print(f"[yellow]Aucun fichier {config} trouvé. Lancement de l'assistant...[/yellow]")
            user_config = run_interactive_wizard(plugins_dir=plugins_dir, output_config_path=config)
            if not user_config:
                raise typer.Exit(code=0)

    engine = SOCDeployEngine(config, plugins_dir)
    try:
        report_path = engine.deploy()
        console.print(f"[bold green]✅ Déploiement terminé. Rapport : {report_path}[/bold green]")
    except Exception as e:
        console.print(f"[bold red]❌ Erreur lors du déploiement : {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command("status")
def status(
    config: Path = typer.Option(Path("config.yaml"), "--config", "-c", help="Fichier de configuration YAML"),
    plugins_dir: Path = typer.Option(Path("plugins"), "--plugins-dir", "-p", help="Dossier des plugins")
):
    """Vérifie l'état actuel des outils déployés."""
    if not config.exists():
        console.print(f"[red]Fichier de configuration {config} introuvable.[/red]")
        raise typer.Exit(code=1)

    engine = SOCDeployEngine(config, plugins_dir)
    engine.load_config()
    state = engine.state_mgr.load()

    if not state:
        console.print(f"[yellow]Aucun service n'est actuellement marqué comme installé pour la stack '{engine.user_config.stack_name}'.[/yellow]")
        return

    table = Table(title=f"État des Services — Stack '{engine.user_config.stack_name}'", show_header=True)
    table.add_column("Outil", style="bold")
    table.add_column("Mode")
    table.add_column("Méthode")
    table.add_column("Statut")
    table.add_column("Installé le")
    table.add_column("URLs")

    for p_name, svc in state.items():
        table.add_row(
            p_name,
            svc.mode,
            svc.method,
            f"[green]{svc.status}[/green]" if svc.status == "installed" else f"[red]{svc.status}[/red]",
            svc.installed_at or "Inconnu",
            ", ".join(svc.urls) or "-"
        )

    console.print(table)


@app.command("destroy")
def destroy(
    tool: Optional[str] = typer.Argument(None, help="Nom spécifique de l'outil à désinstaller (ou omettre pour toute la stack)"),
    config: Path = typer.Option(Path("config.yaml"), "--config", "-c", help="Fichier de configuration YAML"),
    all_stack: bool = typer.Option(False, "--all", help="Confirmer la suppression de toute la stack"),
    plugins_dir: Path = typer.Option(Path("plugins"), "--plugins-dir", "-p", help="Dossier des plugins")
):
    """Désinstalle un outil spécifique ou l'ensemble de la stack SOC."""
    if not config.exists():
        console.print(f"[red]Fichier de configuration {config} introuvable.[/red]")
        raise typer.Exit(code=1)

    engine = SOCDeployEngine(config, plugins_dir)
    if not tool and not all_stack:
        console.print("[yellow]Veuillez spécifier le nom d'un outil ou utiliser --all pour toute la stack.[/yellow]")
        return

    target = tool if tool else None
    msg = f"Désinstallation de '{tool}'" if tool else f"Désinstallation complète de la stack"
    console.print(f"[bold yellow]⚠ {msg}...[/bold yellow]")

    try:
        engine.destroy(plugin_name=target)
        console.print("[bold green]✔ Nettoyage terminé.[/bold green]")
    except Exception as e:
        console.print(f"[bold red]❌ Erreur lors de la désinstallation : {e}[/bold red]")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
