from pathlib import Path
from socdeploy.engine import SOCDeployEngine

config = Path("config.example.yaml")
engine = SOCDeployEngine(config)
try:
    report = engine.deploy()
    print(f"Déploiement réussi, rapport : {report}")
except Exception as e:
    print(f"Erreur : {e}")