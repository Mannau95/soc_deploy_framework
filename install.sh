#!/usr/bin/env bash
# ==============================================================================
# SOC Deploy Framework — Script d'installation automatique pour serveurs Linux
# ==============================================================================
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${CYAN}${BOLD}"
cat << "EOF"
  ____   ___   ____   ____             _             
 / ___| / _ \ / ___| |  _ \  ___ _ __ | | ___  _   _ 
 \___ \| | | | |     | | | |/ _ \ '_ \| |/ _ \| | | |
  ___) | |_| | |___  | |_| |  __/ |_) | | (_) | |_| |
 |____/ \___/ \____| |____/ \___| .__/|_|\___/ \__, |
                                |_|            |___/ 
      Framework de Déploiement SOC Open Source
EOF
echo -e "${NC}"

# 1. Vérification des privilèges root / sudo
if [ "$EUID" -ne 0 ]; then
  echo -e "${YELLOW}Ce script doit être exécuté avec des privilèges administrateur.${NC}"
  echo -e "Relance automatique avec sudo..."
  exec sudo bash "$0" "$@"
fi

echo -e "${GREEN}✔ Exécution avec privilèges administrateur.${NC}"

# 2. Détection de la distribution Linux
DISTRO="unknown"
if [ -f /etc/os-release ]; then
  . /etc/os-release
  DISTRO=$ID
  echo -e "Système détecté : ${BOLD}${PRETTY_NAME}${NC} (ID: ${DISTRO})"
fi

# 3. Installation des prérequis système (git, python3, venv, curl)
echo -e "\n${CYAN}1/4 — Installation des paquets prérequis...${NC}"

case "$DISTRO" in
  ubuntu|debian|kali|mint)
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq git python3 python3-venv python3-pip curl ca-certificates iptables
    ;;
  rhel|centos|rocky|almalinux|fedora)
    dnf install -y -q git python3 python3-pip curl iptables || yum install -y -q git python3 python3-pip curl iptables
    ;;
  opensuse*|sles)
    zypper --non-interactive install git python3 python3-pip python3-virtualenv curl iptables
    ;;
  arch|manjaro)
    pacman -Sy --noconfirm git python python-pip curl iptables
    ;;
  *)
    echo -e "${YELLOW}Distribution non explicitement reconnue, tentative standard...${NC}"
    ;;
esac

echo -e "${GREEN}✔ Paquets système installés.${NC}"

# 4. Vérification et installation de Docker si nécessaire
echo -e "\n${CYAN}2/4 — Vérification de l'environnement Docker...${NC}"

if command -v docker >/dev/null 2>&1; then
  echo -e "${GREEN}✔ Docker est déjà installé : $(docker --version)${NC}"
else
  echo -e "${YELLOW}Docker n'a pas été détecté sur ce serveur.${NC}"
  read -p "Voulez-vous installer Docker automatiquement via le script officiel ? [O/n] " -r REPLY
  REPLY=${REPLY:-O}
  if [[ $REPLY =~ ^[Oo]$ ]]; then
    echo -e "Installation de Docker en cours..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable --now docker
    echo -e "${GREEN}✔ Docker installé avec succès.${NC}"
  else
    echo -e "${YELLOW}Poursuite sans Docker (seules les méthodes d'installation natives seront fonctionnelles).${NC}"
  fi
fi

# 5. Déploiement du code source du Framework
echo -e "\n${CYAN}3/4 — Configuration du SOC Deploy Framework...${NC}"

# Si le script est exécuté depuis le dépôt cloné, utiliser ce dossier
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/soc_deploy_framework"

if [ -f "${SCRIPT_DIR}/pyproject.toml" ]; then
  TARGET_DIR="${SCRIPT_DIR}"
  echo -e "Utilisation du dossier courant : ${BOLD}${TARGET_DIR}${NC}"
else
  TARGET_DIR="${INSTALL_DIR}"
  echo -e "Installation dans : ${BOLD}${TARGET_DIR}${NC}"
  mkdir -p "${TARGET_DIR}"
  # Cloner le dépôt si nécessaire
  if [ ! -f "${TARGET_DIR}/pyproject.toml" ]; then
    git clone https://github.com/your-org/soc_deploy_framework.git "${TARGET_DIR}"
  fi
fi

# 6. Création de l'environnement virtuel Python et installation
echo -e "\n${CYAN}4/4 — Installation de l'environnement Python...${NC}"
cd "${TARGET_DIR}"

if [ ! -d "venv" ]; then
  python3 -m venv venv
fi

# Activer et installer
source venv/bin/activate
pip install --quiet --upgrade pip
pip install --quiet -e .

# Créer un lien symbolique global /usr/local/bin/socdeploy
ln -sf "${TARGET_DIR}/venv/bin/socdeploy" /usr/local/bin/socdeploy
chmod +x /usr/local/bin/socdeploy

echo -e "\n${GREEN}${BOLD}========================================================================${NC}"
echo -e "${GREEN}${BOLD}✔ SOC Deploy Framework a été installé avec succès !${NC}"
echo -e "${GREEN}${BOLD}========================================================================${NC}"
echo -e "\nVous pouvez maintenant lancer le framework depuis n'importe où avec la commande :"
echo -e "\n   ${BOLD}sudo socdeploy${NC}\n"
echo -e "Commandes disponibles :"
echo -e "   • ${BOLD}socdeploy list${NC}       : Afficher le catalogue des 6 outils SOC"
echo -e "   • ${BOLD}socdeploy info <nom>${NC} : Détail d'un outil (modes, variables)"
echo -e "   • ${BOLD}socdeploy status${NC}     : État des services déployés"
echo -e "   • ${BOLD}socdeploy destroy${NC}    : Désinstaller un outil ou toute la stack\n"
