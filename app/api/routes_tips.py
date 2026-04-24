from fastapi import APIRouter, Query


router = APIRouter(prefix="/api", tags=["tips"])


@router.get("/tips")
def tips(scope_type: str = Query("total"), scope_id: str | None = Query(None)):
    return {
        "scope": {"type": scope_type, "id": scope_id},
        "tips": [
            {
                "title": "Stoßlüften statt Kipplüften",
                "description": "3-5 Minuten querlüften, danach Fenster schließen. Das senkt Wärmeverlust und Feuchterisiko.",
                "category": "Lüften",
                "estimated_impact": "mittel",
            },
            {
                "title": "Heizkörper freihalten",
                "description": "Möbel, Vorhänge und Verkleidungen entfernen. Wärme verteilt sich schneller und gleichmäßiger.",
                "category": "Heizen",
                "estimated_impact": "niedrig",
            },
            {
                "title": "Temperatur fein senken",
                "description": "Ein Grad weniger spart spürbar Energie. Wohnräume moderat, Nebenräume bewusst niedriger halten.",
                "category": "Komfort",
                "estimated_impact": "hoch",
            },
            {
                "title": "Ausreißer gezielt prüfen",
                "description": "Dauerhaft hohe Wohnungen priorisieren: Thermostate, Fensterverhalten und Leerstand abgleichen.",
                "category": "Analyse",
                "estimated_impact": "mittel",
            },
        ],
    }
