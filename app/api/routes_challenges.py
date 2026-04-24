from fastapi import APIRouter


router = APIRouter(prefix="/api", tags=["challenges"])


@router.get("/challenges")
def challenges():
    return {
        "challenges": [
            {
                "title": "Senken Sie den Monatsverbrauch um 8 %",
                "description": "Bleiben Sie im aktuellen Monat mindestens 8 % unter dem erwarteten Heizenergieverbrauch.",
                "progress": 5.1,
                "goal": 8,
                "progress_label": "5,1 % von 8 %",
                "reward": "50 € Servicegutschrift",
                "enabled": True,
                "locked_reason": None,
                "category": "Energie",
            },
            {
                "title": "Verbrauchsanomalien prüfen",
                "description": "Prüfen Sie 7 auffällige Verbrauchstage und markieren Sie die Ursache im Report.",
                "progress": 4,
                "goal": 7,
                "progress_label": "4 von 7 Tagen geprüft",
                "reward": "Analyse-Gutschrift",
                "enabled": True,
                "locked_reason": None,
                "category": "Stabilität",
            },
            {
                "title": "Heizen bei offenem Fenster stoppen",
                "description": "Multisensor erkennt kritische Lüftungsphasen.",
                "progress": 0,
                "goal": 1,
                "progress_label": "Sensorik fehlt",
                "reward": "15 % des Kaufpreises zurück",
                "enabled": False,
                "locked_reason": "Für diese Challenge fehlt aktuell der Techem Multisensor Plus in der Immobilie.",
                "category": "Produkt-Upgrade",
                "product_name": "Techem Multisensor Plus",
                "product_url": "https://www.techem.com/de/de/geraete/multisensorplus",
                "cta_label": "Produkt ansehen",
                "visual": "multisensor-plus",
                "product_image_url": "https://media.techem.com/is/image/techem/241211_Techem_Produktseite_Mieter_Bildteaser_1500x1125_05?qlt=85&wid=600&ts=1769015268930&dpr=off",
            },
            {
                "title": "Schimmelrisiko früher erkennen",
                "description": "Raumklima-Hinweise für frühe Prävention.",
                "progress": 0,
                "goal": 1,
                "progress_label": "Service fehlt",
                "reward": "15 % Servicegutschrift",
                "enabled": False,
                "locked_reason": "Für diese Challenge wird zusätzliche Raumklima-Sensorik mit Techem Multisensor Plus benötigt.",
                "category": "Prävention",
                "product_name": "Raumklima-Service mit Multisensor Plus",
                "product_url": "https://www.techem.com/de/de/geraete/multisensorplus/rks",
                "cta_label": "Produkt ansehen",
                "visual": "multisensor-plus",
                "product_image_url": "https://media.techem.com/is/image/techem/241211_Techem_Produktseite_Mieter_Bildteaser_1500x1125_05?qlt=85&wid=600&ts=1769015268930&dpr=off",
            },
        ]
    }






