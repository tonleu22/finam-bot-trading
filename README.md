\# 🇷🇺 Bot de Trading — Actions Russes (MOEX)



Un bot de trading automatisé pour les actions russes, avec alertes Telegram en temps réel.



\## 🚀 Fonctionnalités



\- 📊 Récupération des cours en direct depuis l'API MOEX

\- 📈 Stratégie SMA (moyennes mobiles) 5/20

\- 💰 Portefeuille virtuel avec suivi des gains/pertes

\- 🛑 Stop-loss automatique à -5%

\- 🤖 Alertes Telegram instantanées à chaque signal

\- 💾 Sauvegarde de l'état du portefeuille



\## 📁 Structure du projet



| Fichier | Description |

|---------|-------------|

| `bot\_telegram.py` | Bot principal avec alertes Telegram |

| `bot\_portefeuille.py` | Bot avec portefeuille virtuel |

| `bot\_live.py` | Détection de signaux en direct |

| `test\_connexion.py` | Test de connexion à l'API Finam |

| `test\_telegram.py` | Test d'envoi Telegram |



\## 🛠️ Technologies utilisées



\- \*\*Python 3.13\*\*

\- \*\*requests\*\* — Appels API

\- \*\*pandas\*\* — Analyse de données

\- \*\*python-dotenv\*\* — Gestion des variables d'environnement

\- \*\*Telegram Bot API\*\* — Notifications en temps réel

\- \*\*MOEX ISS API\*\* — Données de marché



\## ⚙️ Installation



```bash

git clone https://github.com/tonleu22/finam-bot-trading.git

cd finam-bot-trading

python -m venv venv

venv\\Scripts\\activate

pip install requests pandas python-dotenv

