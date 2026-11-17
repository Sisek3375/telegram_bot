"""
Bot Telegram d'alerte BTCUSD (gratuit, sans dépendance externe).

Prévient quand le prix du Bitcoin franchit un seuil, à la hausse ou à la baisse.
Deux modes :
  python bot.py          -> une seule vérification (utilisé par GitHub Actions)
  python bot.py --boucle -> tourne en continu sur votre ordinateur (vérif toutes les 60 s)

Variables d'environnement requises :
  TELEGRAM_TOKEN   : le jeton donné par @BotFather
  TELEGRAM_CHAT_ID : votre identifiant de discussion
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request

# ---- Réglages -------------------------------------------------------------
SEUILS = [30_000, 61_000, 99_500]   # ajoutez/retirez des seuils ici
INTERVALLE_BOUCLE = 60              # secondes entre deux vérifs en mode --boucle
FICHIER_ETAT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "etat.json")
# ---------------------------------------------------------------------------

TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "btc-alert-bot"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def prix_btc():
    """Prix BTC en USD via des API publiques gratuites (sans clé)."""
    if os.environ.get("PRIX_TEST"):            # pour tester sans réseau
        return float(os.environ["PRIX_TEST"])
    sources = [
        ("Coinbase", "https://api.coinbase.com/v2/prices/BTC-USD/spot",
         lambda d: d["data"]["amount"]),
        ("Kraken", "https://api.kraken.com/0/public/Ticker?pair=XBTUSD",
         lambda d: next(iter(d["result"].values()))["c"][0]),
        ("CoinGecko", "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
         lambda d: d["bitcoin"]["usd"]),
    ]
    for nom, url, extraire in sources:
        try:
            return float(extraire(_get_json(url)))
        except Exception as e:
            print(f"[{nom}] indisponible : {e}")
    raise RuntimeError("Aucune source de prix disponible")


def envoyer_telegram(texte):
    if not TOKEN or not CHAT_ID:
        print("(Telegram non configuré) " + texte)
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": texte}).encode()
    urllib.request.urlopen(url, data=data, timeout=15)


def charger_etat():
    try:
        with open(FICHIER_ETAT) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def sauver_etat(etat):
    with open(FICHIER_ETAT, "w") as f:
        json.dump(etat, f, indent=2, sort_keys=True)


def verifier():
    prix = prix_btc()
    etat = charger_etat()       # ex. {"61000": "dessus", "30000": "dessus", ...}
    nouvel_etat = {}
    messages = []

    for seuil in sorted(SEUILS):
        cle = str(seuil)
        position = "dessus" if prix >= seuil else "dessous"
        nouvel_etat[cle] = position
        ancienne = etat.get(cle)
        if ancienne and ancienne != position:
            if position == "dessus":
                messages.append(f"🟢 BTCUSD monte au-dessus de {seuil:,.0f} $".replace(",", " "))
            else:
                messages.append(f"🔴 BTCUSD baisse en dessous de {seuil:,.0f} $".replace(",", " "))

    prix_txt = f"{prix:,.0f}".replace(",", " ")
    if messages:
        envoyer_telegram("\n".join(messages) + f"\nPrix actuel : {prix_txt} $")
    elif not etat:
        envoyer_telegram(f"✅ Bot d'alerte BTC démarré. Prix actuel : {prix_txt} $\n"
                         f"Seuils surveillés : " + ", ".join(f"{s:,}".replace(",", " ") for s in SEUILS))

    if nouvel_etat != etat:
        sauver_etat(nouvel_etat)
    print(f"Prix : {prix_txt} $ | alertes : {len(messages)}")


if __name__ == "__main__":
    if "--boucle" in sys.argv:
        while True:
            try:
                verifier()
            except Exception as e:
                print(f"Erreur : {e}")
            time.sleep(INTERVALLE_BOUCLE)
    else:
        verifier()
