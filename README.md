# 🛡️ SOC Deploy Framework

> **SOC Deploy Framework** est un outil en ligne de commande (CLI) permettant de déployer automatiquement et de manière modulaire une stack complète de cybersécurité (SOC open source) sur des serveurs Linux.

L'utilisateur peut parcourir le catalogue des outils disponibles, sélectionner via un **menu interactif** uniquement les outils souhaités, choisir leur mode opératoire (ex: IDS passif vs IPS actif) ainsi que la méthode de déploiement (Docker ou natif), et obtenir un **rapport de déploiement** complet avec tous les accès et identifiants.

---

## 🚀 Fonctionnalités Clés

- **Catalogue modulaire extensible** : Système de plugins basé sur des manifestes YAML standardisés (`manifest.yaml`).
- **Menu interactif dans le terminal** : Sélection des outils par cases à cocher, choix des modes et des méthodes, et configuration des variables assistée.
- **Support Multi-OS** : Détection automatique de la distribution Linux hôte (famille Debian/Ubuntu, RHEL/Rocky, SUSE...).
- **Conteneurs ou Natif** : Choix par outil entre déploiement Docker Compose ou installation native (paquets système / scripts officiels).
- **Sécurité et Idempotence** :
  - Mode IPS Suricata sécurisé avec `--queue-bypass` et vérification anti-doublon d'iptables.
  - Fichier d'état (`stack_state.json`) pour ne réinstaller que les outils modifiés ou manquants.
  - Rollback propre et ciblé en cas d'erreur.
- **Corrélation Automatique SIEM ↔ NIDS** : Détection automatique des outils compatibles (ex: Suricata et Wazuh). L'ingestion du flux d'alertes `eve.json` dans Wazuh est automatiquement configurée (décodeurs JSON, règles Wazuh 86600+).
- **Rapports détaillés** : Génération automatique d'un rapport Markdown (`report.md`) et d'un tableau récapitulatif dans le terminal (URLs, mots de passe, fichiers de logs).

---

## 📦 Outils SOC Disponibles

| Outil | Catégorie | Modes disponibles | Méthodes |
| :--- | :--- | :--- | :--- |
| **Wazuh** | SIEM / XDR | `auto-install` (All-in-one officiel), `single-node` | Natif, Docker |
| **Suricata** | NIDS / NIPS | `ids` (détection passive), `ips` (prévention active NFQUEUE) | Docker, Natif |
| **TheHive & Cortex** | Gestion des Incidents (SIRP) | `thehive-standalone` (TheHive 5 + Cassandra + MinIO), `thehive-cortex` | Docker |
| **MISP** | Cyber Threat Intelligence (CTI) | `standard` (MISP Core + MariaDB + Redis) | Docker |
| **Zeek** | Analyse Réseau & Métadonnées | `live-capture` (inspection en direct AF_PACKET/Promiscuous) | Docker |
| **Velociraptor** | Détection & EDR / DFIR | `server` (Console GUI + Frontend agents VQL) | Docker |

---

## 🛠️ Installation

### Prérequis
- Système d'exploitation : **Linux** (Debian 11+, Ubuntu 20.04+, RHEL/Rocky 8+)
- Python **>= 3.9**
- Docker & Docker Compose (si utilisation de conteneurs)
- Privilèges `sudo` ou `root`

### Installation rapide (serveur Linux)

Exécutez simplement le script d'installation automatisé en une seule commande :

```bash
sudo bash install.sh
```

Ce script vérifie et installe automatiquement :
- Les dépendances système requises (`git`, `python3`, `python3-venv`, `curl`, `iptables`).
- Docker et Docker Compose (si non présents).
- L'environnement virtuel Python isolé.
- Le binaire global `/usr/local/bin/socdeploy` pour lancer le framework de n'importe où.

### Installation manuelle

```bash
# Cloner le dépôt
git clone https://github.com/your-org/soc_deploy_framework.git
cd soc_deploy_framework

# Créer l'environnement virtuel
python3 -m venv venv
source venv/bin/activate

# Installer les dépendances
pip install -e .
```

---

## 💻 Utilisation de la CLI

### 1. Assistant interactif complet (recommandé)
Lancez simplement `socdeploy` (ou `sudo socdeploy`) sans argument :
```bash
sudo ./venv/bin/socdeploy
```
L'assistant détectera votre machine hôte, vous présentera les outils à cocher avec la barre d'espace, vous demandera les modes et variables, puis vous proposera de lancer l'installation immédiatement.

### 2. Consulter le catalogue des outils
```bash
socdeploy list
```

### 3. Obtenir les détails d'un outil
```bash
socdeploy info suricata
socdeploy info wazuh
```

### 4. Générer une configuration sans déployer
```bash
socdeploy init -o config.yaml
```

### 5. Déployer à partir d'un fichier YAML
```bash
socdeploy deploy -c config.yaml
```

### 6. Vérifier l'état des services déployés
```bash
socdeploy status -c config.yaml
```

### 7. Désinstaller un outil ou toute la stack
```bash
# Désinstaller un outil spécifique
socdeploy destroy suricata -c config.yaml

# Désinstaller toute la stack
socdeploy destroy --all -c config.yaml
```

---

## 🧩 Structure d'un Plugin

Chaque plugin réside dans le dossier `plugins/<nom_plugin>/` :

```text
plugins/mon-outil/
├── manifest.yaml           # Métadonnées, modes, méthodes, exigences et variables
├── hooks.py                # Cycle de vie (pre_install, install, post_install, uninstall, credentials)
├── templates/              # Templates Jinja2 (docker-compose.yml.j2, etc.)
└── config/                 # Fichiers de configuration de l'outil
```

### Exemple de `manifest.yaml` :
```yaml
name: mon-outil
display_name: "Mon Outil SOC"
version: "1.0.0"
category: incident          # siem | network | edr | incident | threat-intel | soar
description: "Description courte de l'outil"
homepage: "https://example.com"

modes:
  default:
    description: "Mode standard"
    methods:
      docker:
        templates:
          - docker-compose.yml.j2
        supported_os: [all]
    requirements:
      min_ram_mb: 2048
      min_cpu: 2
      ports: [9000]
      docker: true
    variables:
      - name: admin_email
        prompt: "Adresse email administrateur"
        type: str
        default: "admin@soc.local"
    healthcheck:
      type: http
      url: "http://localhost:9000"
      expected_status: 200
```

---

## 🧪 Tests

Les tests unitaires couvrent le catalogue, la validation des manifestes, le rendu des templates et la génération des rapports sans dépendance à Docker :

```bash
pytest -v
```

---

## 📄 Licence
Ce projet est distribué sous licence Apache-2.0.
