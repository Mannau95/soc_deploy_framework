"""Menu interactif de sélection et de configuration pour SOC Deploy Framework."""

from pathlib import Path
from typing import Dict, Any, List, Optional
import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from socdeploy.models import UserConfig, ToolConfig
from socdeploy.catalog import PluginCatalog, CATEGORY_LABELS
from socdeploy.system import system
from socdeploy.utils import generate_secure_password


import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

console = Console(legacy_windows=False)


def run_interactive_wizard(
    plugins_dir: Path = Path("plugins"),
    output_config_path: Optional[Path] = None
) -> Optional[UserConfig]:
    """Guide l'utilisateur dans le choix des outils, de leurs modes et variables."""
    catalog = PluginCatalog(plugins_dir)
    plugins = catalog.list_plugins()

    if not plugins:
        console.print("[bold red]Aucun plugin SOC trouvé dans le dossier 'plugins/' ![/bold red]")
        return None

    # 1. En-tête avec les informations système
    sys_info = system.to_dict()
    docker_status = "[green]✔ Opérationnel[/green]" if sys_info["docker_available"] else "[yellow]⚠ Non détecté[/yellow]"
    root_status = "[green]✔ Root[/green]" if sys_info["is_root"] else "[yellow]Utilisateur standard[/yellow]"

    panel_text = (
        f"[bold cyan]Système :[/bold cyan] {sys_info['distro']} (famille {sys_info['os_family']})\n"
        f"[bold cyan]Ressources :[/bold cyan] {sys_info['ram_mb']} Mo RAM · {sys_info['cpu_count']} vCPU\n"
        f"[bold cyan]Environnement :[/bold cyan] Docker : {docker_status} · Privilèges : {root_status}"
    )
    console.print(Panel(panel_text, title="🛡️ SOC Deploy Framework — Assistant d'installation", border_style="cyan"))

    # 2. Nom de la stack
    stack_name = questionary.text(
        "Nom de votre environnement / stack SOC :",
        default="lab-soc"
    ).ask()
    if not stack_name:
        return None

    # 3. Choix des outils à installer
    choices = []
    for cat_key, cat_label in CATEGORY_LABELS.items():
        cat_plugins = [p for p in plugins if p.category == cat_key]
        if cat_plugins:
            choices.append(questionary.Separator(f"── {cat_label} ──"))
            for p in cat_plugins:
                title = f"{p.label} (v{p.version})"
                if p.description:
                    title += f" - {p.description[:60]}..."
                choices.append(questionary.Choice(title=title, value=p.name))

    other_plugins = [p for p in plugins if p.category not in CATEGORY_LABELS]
    if other_plugins:
        choices.append(questionary.Separator("── Autres outils ──"))
        for p in other_plugins:
            choices.append(questionary.Choice(title=p.label, value=p.name))

    selected_plugins = questionary.checkbox(
        "Sélectionnez les outils SOC que vous souhaitez installer (Espace pour cocher, Entrée pour valider) :",
        choices=choices
    ).ask()

    if not selected_plugins:
        console.print("[yellow]Aucun outil sélectionné. Annulation.[/yellow]")
        return None

    # 4. Configuration détaillée pour chaque outil choisi
    tools_config: List[ToolConfig] = []

    for plugin_name in selected_plugins:
        manifest = catalog.get_plugin(plugin_name)
        if not manifest:
            continue

        console.print(f"\n[bold green]Configuration de {manifest.label} :[/bold green]")

        # Choix du mode
        mode_choices = [
            questionary.Choice(
                title=f"{mode_name} : {mode_cfg.description}",
                value=mode_name
            )
            for mode_name, mode_cfg in manifest.modes.items()
        ]

        if len(mode_choices) == 1:
            chosen_mode = mode_choices[0].value
        else:
            chosen_mode = questionary.select(
                f"Mode pour {manifest.label} :",
                choices=mode_choices
            ).ask()

        mode_config = manifest.modes[chosen_mode]

        # Choix de la méthode (docker / native)
        available_methods = catalog.get_compatible_methods(plugin_name, chosen_mode, system.os_family)
        if not available_methods:
            available_methods = ["docker"]

        if len(available_methods) == 1:
            chosen_method = available_methods[0]
            console.print(f"  Méthode d'installation : [cyan]{chosen_method}[/cyan] (seule compatible)")
        else:
            chosen_method = questionary.select(
                f"Méthode d'installation pour {manifest.label} :",
                choices=[
                    questionary.Choice(title="Conteneur Docker (recommandé)", value="docker"),
                    questionary.Choice(title="Installation native sur le système (paquets / script)", value="native")
                ]
            ).ask()

        # Variables requises
        variables: Dict[str, Any] = {}
        for var in mode_config.variables:
            prompt = f"  {var.prompt} :"

            if var.type == "bool":
                ans = questionary.confirm(prompt, default=bool(var.default)).ask()
            elif var.type == "choice":
                opts = var.choices or []
                if var.choices_from == "network_interfaces":
                    opts = system.get_network_interfaces()
                ans = questionary.select(prompt, choices=opts, default=opts[0] if opts else "").ask()
            elif var.type == "password":
                ans = questionary.password(f"{prompt} [Entrée pour générer un mot de passe fort]").ask()
                if not ans:
                    ans = generate_secure_password(16)
                    console.print(f"    [dim cyan]✔ Mot de passe généré automatiquement : [bold]{ans}[/bold][/dim cyan]")
            else:
                default_val = str(var.default) if var.default is not None else ""
                ans = questionary.text(prompt, default=default_val).ask()

            variables[var.name] = ans

        tools_config.append(
            ToolConfig(
                plugin=plugin_name,
                mode=chosen_mode,
                method=chosen_method,
                variables=variables
            )
        )

    # 5. Interconnexions automatiques (chaîne complète SOC)
    integrations: List[str] = []
    has_wazuh = any(t.plugin == "wazuh" for t in tools_config)
    has_suricata = any(t.plugin == "suricata" for t in tools_config)
    has_zeek = any(t.plugin == "zeek" for t in tools_config)
    has_thehive = any(t.plugin == "thehive" for t in tools_config)
    has_misp = any(t.plugin == "misp" for t in tools_config)

    found_integrations = (
        (has_wazuh and has_suricata) or
        (has_wazuh and has_zeek) or
        (has_wazuh and has_thehive) or
        (has_thehive and has_misp)
    )

    if found_integrations:
        console.print("\n[bold cyan]🔗 Détection d'interconnexions et corrélations SOC possibles :[/bold cyan]")

        if has_wazuh and has_suricata:
            if questionary.confirm("Interconnecter Suricata à Wazuh (alertes réseau eve.json -> SIEM) ?", default=True).ask():
                integrations.append("wazuh_suricata")
                console.print("  [green]✔ Corrélation Suricata ➔ Wazuh activée.[/green]")

        if has_wazuh and has_zeek:
            if questionary.confirm("Interconnecter Zeek à Wazuh (métadonnées réseau dns/conn/notice -> SIEM) ?", default=True).ask():
                integrations.append("wazuh_zeek")
                console.print("  [green]✔ Corrélation Zeek ➔ Wazuh activée.[/green]")

        if has_wazuh and has_thehive:
            if questionary.confirm("Interconnecter Wazuh à TheHive (génération automatique d'incidents pour alertes critiques) ?", default=True).ask():
                integrations.append("wazuh_thehive")
                console.print("  [green]✔ Escalade Wazuh ➔ TheHive activée.[/green]")

        if has_thehive and has_misp:
            if questionary.confirm("Interconnecter TheHive à MISP (enrichissement des observables via la threat intelligence) ?", default=True).ask():
                integrations.append("thehive_misp")
                console.print("  [green]✔ CTI TheHive ↔ MISP activée.[/green]")

    user_config = UserConfig(
        stack_name=stack_name,
        tools=tools_config,
        integrations=integrations
    )

    # 5. Récapitulatif
    console.print("\n[bold]Plan de déploiement sélectionné :[/bold]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Outil")
    table.add_column("Mode")
    table.add_column("Méthode")
    table.add_column("Paramètres")

    for t in tools_config:
        params = ", ".join(f"{k}={v}" for k, v in t.variables.items() if not k.endswith("password"))
        table.add_row(t.plugin, t.mode, t.method, params or "Défaut")
    console.print(table)

    # 6. Sauvegarde du fichier config.yaml
    if not output_config_path:
        output_config_path = Path("config.yaml")

    import yaml
    with open(output_config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(user_config.model_dump(), f, sort_keys=False, allow_unicode=True)
    console.print(f"[green]Configuration enregistrée dans : [bold]{output_config_path}[/bold][/green]")

    return user_config
