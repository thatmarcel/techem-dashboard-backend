# Heating Energy Analysis Demo API

Lokaler Demo-Prototyp fuer ein Heizenergie-Analyse-System fuer Vermieter.
Das Backend liest CSV-Dateien ein, normalisiert sie, speichert sie in SQLite und stellt JSON-APIs fuer ein separates Frontend bereit.

## 1. Installation

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Mit `uv` geht es fuer dieses Projekt so:

```powershell
cd backend
$env:UV_CACHE_DIR=".uv-cache"
$env:UV_PYTHON_INSTALL_DIR=".uv-python"
uv python install 3.12
uv venv --python 3.12 --clear .venv
uv pip install -r requirements.txt
```

Wenn der Editor meldet, dass `pydantic`, `fastapi` oder `pandas` nicht gefunden werden, ist fast immer der falsche Python-Interpreter aktiv oder die Dependencies wurden noch nicht installiert. In VS Code: `Python: Select Interpreter` ausfuehren und `backend/.venv/Scripts/python.exe` auswaehlen. Danach Terminal neu oeffnen und bei Bedarf nochmal `pip install -r requirements.txt` ausfuehren.

## 2. .env konfigurieren

```powershell
Copy-Item .env.example .env
```

Wichtige Werte:

```env
TOMORROW_API_KEY=
WEATHER_PROVIDER=auto
GOOGLE_API_KEY=
GOOGLE_AI_PROVIDER=gemini
GOOGLE_AI_MODEL=gemini-1.5-flash
GOOGLE_CHAT_SYSTEM_PROMPT_FILE=prompts/chat_system_prompt.txt
VERTEX_PROJECT_ID=
VERTEX_LOCATION=
VERTEX_ENDPOINT_ID=
DATABASE_URL=sqlite:///./demo.db
ENERGY_PRICE_EUR_PER_KWH=0.12
```

Ohne API-Keys startet das System trotzdem. Wetter nutzt lokale Fallbacks; Graph/Report nutzen den lokalen Standardalgorithmus.

`WEATHER_PROVIDER` unterstuetzt:

- `auto`: Open-Meteo fuer historische und nah zukuenftige Zeitraeume, Tomorrow.io nur noch als schmaler Realtime-Zusatz fuer heute
- `open_meteo`: nur Open-Meteo plus lokaler Fallback
- `tomorrow`: nur Tomorrow.io-Realtime fuer heute plus lokaler Fallback
- `local`: lokaler Standardalgorithmus für Graph/Report ohne externes AI-Modell

Fuer laengere oder mehrzeilige Chat-Systemprompts bitte die Datei `backend/prompts/chat_system_prompt.txt` bearbeiten. Das ist robuster als ein langer `.env`-Wert und vermeidet Probleme mit Editor-Highlighting, Kommentaren oder Zeilenumbruechen.

## 3. Starten

```powershell
uvicorn app.main:app --reload
```

Frontend lokal dazu starten:

```powershell
cd ..
.\backend\.venv\Scripts\python.exe -m http.server 3000 --bind 127.0.0.1 --directory frontend
```

Automatisierter Start aus dem Projektroot:

```powershell
cd ..
.\backend\.venv\Scripts\python.exe .\start_demo.py
```

Das Skript startet Backend und Frontend, wartet auf beide Endpunkte und oeffnet danach bevorzugt Opera GX mit dem Dashboard und den Backend-Docs. Wenn Opera GX lokal nicht gefunden wird, faellt es auf den Standardbrowser zurueck.

API-Dokumentation:

- Swagger UI: http://127.0.0.1:8000/docs
- Healthcheck: http://127.0.0.1:8000/api/health
- Frontend Dashboard: http://127.0.0.1:3000/

## 4. CSV-Ordnerstruktur

Demo-Daten liegen in:

```text
backend/data/sample_csvs/
```

Import:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/import/csv-directory `
  -ContentType "application/json" `
  -Body '{"directory_path":"data/sample_csvs"}'
```

Erwartete interne Spalten:

- date
- zipcode
- city
- street
- housenumber
- apartment_number
- energysource
- energyusage_kwh
- livingspace_m2
- mean_outside_temperature_c
- roomnumber
- emission_factor_g_per_kwh
- unitnumber

Euer CSV-Format wird direkt unterstuetzt, z. B.:

```csv
date,zipcode,energysource,city,energyusage [kWh],livingspace [mÂ²],mean outside temperature [Â°C],roomnumber,emission factor [g/kWh],unitnumber,full_address
2019-12-31,6110,Erdgas,Halle,0.71,9.4,4.1,1,181.39,1,"Merseburger StraÃŸe 12, 06110"
```

Die Importlogik normalisiert Spaltennamen robust: lowercase, Sonderzeichen zu `_`, bekannte Aliase wie `postal_code`, `energy_usage_kwh`, `energyusage [kWh]`, `livingspace [mÂ²]`, `emission factor [g/kWh]`, `house_number`, `apartment` und `living_area_m2` werden auf die interne Zielsicht gemappt.

Wenn `street` und `housenumber` fehlen, werden sie aus `full_address` abgeleitet. Wenn `apartment_number` fehlt, wird `unitnumber` als Wohnungsnummer verwendet. Deutsche Postleitzahlen werden auf 5 Stellen normalisiert, also z. B. `6110` zu `06110`.

Interne IDs:

- `city_id`: aus Stadtname
- `building_id`: aus Stadt + Strasse + Hausnummer
- `apartment_id`: aus building_id + Wohnungsnummer

## 5. Beispiel-Requests

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/navigation/overview
Invoke-RestMethod http://127.0.0.1:8000/api/navigation/cities/frankfurt
Invoke-RestMethod http://127.0.0.1:8000/api/search/suggestions?q=Wohnung%208
Invoke-RestMethod "http://127.0.0.1:8000/api/chart?scope_type=total&period=year&analysis_provider=local"
Invoke-RestMethod "http://127.0.0.1:8000/api/report?scope_type=city&scope_id=frankfurt&period=month&analysis_provider=local"
```

Chat:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/chat `
  -ContentType "application/json" `
  -Body '{"message":"Welche Stadt verursacht aktuell am meisten CO2?","use_current_scope":false,"analysis_provider":"gemini"}'
```

Chat mit Gemini, zusaetzlichem System-Hinweis und selektivem Dateikontext:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/api/chat `
  -ContentType "application/json" `
  -Body '{
    "message":"Beziehe dich auf die geoeffnete Wohnung und erklaere die wichtigsten Auffaelligkeiten.",
    "use_current_scope":true,
    "scope_type":"apartment",
    "scope_id":"frankfurt-kapellstrasse-3-apartment-8",
    "period":"month",
    "offset":0,
    "analysis_provider":"gemini",
    "additional_instructions":"Antworte knapp und fuer einen Vermieter verstaendlich.",
    "context_file_paths":["data/sample_csvs/frankfurt_kapellstrasse.csv"]
  }'
```

## 6. Architektur

```text
backend/
  app/
    main.py
    config.py
    db.py
    api/
    schemas/
    services/
    utils/
  data/sample_csvs/
  tests/
  requirements.txt
  .env.example
  README.md
```

Trennung:

- `api/`: FastAPI-Routen, nur Request/Response-Verhalten
- `services/`: Import, Aggregation, Wetter, Feiertage, AI, Report und Chat
- `utils/`: Datumslogik und CSV-Normalisierung
- `schemas/`: Pydantic-Modelle fuer Requests und AI-Antworten
- `db.py`: kleine SQLite-Schicht ohne ORM

## 7. Harte Datenlogik vs. AI-Analyse

Deterministisch im Backend:

- CSV-Validierung und Normalisierung
- SQLite-Speicherung
- Scope-Filter fuer Gesamtbestand, Stadt, Gebaeude, Wohnung
- Summen fuer Energie, CO2 und geschaetzte Kosten
- Suchvorschlaege
- Zeitraeume, Offsets und Diagramm-Achsen
- Ist-Verbrauch und Ist-CO2

AI-Aufgaben:

- Forecast fuer `predicted_energy` und `predicted_co2`
- konservative Optimierung fuer `optimized_energy` und `optimized_co2`
- Einflussanalyse
- Report-Texte
- Chat-Antworten

Das Backend bereitet nur verdichtete Kontextdaten fuer die AI vor. AI-Antworten muessen in ein Pydantic-Schema passen. Bei Fehlern wird automatisch der lokaler Fallback verwendet.

## 8. lokaler Fallbacks

Ohne `TOMORROW_API_KEY`:

- Open-Meteo kann trotzdem historische und nah zukuenftige Wetterdaten fuer den angefragten Zeitraum liefern
- wenn auch Open-Meteo oder Geocoding nicht greift: Temperatur aus CSV, dazu Niederschlag, Frost, Wind und Bewoelkung als lokaler Demo-Kontext

Ohne `GOOGLE_API_KEY`:

- `analysis_provider=gemini` faellt automatisch auf `local` zurueck
- Forecast und Optimierung bleiben lokal startbar

Feiertage:

- lokale deutsche Feiertagslogik
- Bundesland wird grob aus der ersten PLZ-Ziffer abgeleitet
- Fallback ist `DE`, wenn keine Zuordnung moeglich ist

## 9. Gemini-Nutzung

Setze in `.env`:

```env
GOOGLE_API_KEY=...
GOOGLE_AI_PROVIDER=gemini
GOOGLE_AI_MODEL=gemini-1.5-flash
GOOGLE_CHAT_SYSTEM_PROMPT_FILE=prompts/chat_system_prompt.txt
```

Der Gemini-Adapter sendet strukturierte Kontextdaten und eine Schema-Beschreibung an die Gemini API. Die Antwort wird als JSON geparst und gegen Pydantic validiert.

Empfehlung:

- kurze Einzeiler koennen weiterhin optional ueber `GOOGLE_CHAT_SYSTEM_PROMPT` gesetzt werden
- echte mehrzeilige Systemprompts gehoeren in `backend/prompts/chat_system_prompt.txt`

Fuer den Chat gilt jetzt:

- der API-Key wird nur serverseitig aus `.env` gelesen
- der Key wird im HTTP-Header an Google gesendet, nicht an das Frontend zurueckgegeben
- das Frontend sendet nur die Nutzerfrage und optional kleine Zusatzhinweise
- der Backend-Chat sendet standardmaessig nur verdichteten Scope-Kontext:
  - Scope
  - Zeitraum
  - Summary
  - aggregierte Serien
  - Auffaelligkeiten
  - AI-Erklaerungen
- optionale Dateien koennen selektiv ueber `context_file_paths` referenziert werden
- diese Dateien muessen innerhalb von `backend/` liegen
- es werden nur kurze Auszuege uebertragen, keine kompletten Rohdatenordner

Damit muss der Chat nicht bei jeder Frage alle CSV-Quelldaten hochladen. Die Grundidee ist: harte Kennzahlen bleiben lokal, der Chat sieht nur die fuer die aktuelle Frage noetigen verdichteten Daten plus optionale kurze Datei-Auszuege.

## 10. Vertex spaeter anbinden

Der `VertexProvider` hat dieselbe interne Schnittstelle wie der lokale Chart-Provider:

- `analyze_chart(context)`
- `generate_report(context)`
- `chat(context, message)`

Für einen echten Vertex-Endpoint müssen `VERTEX_PROJECT_ID`, `VERTEX_LOCATION`, `VERTEX_ENDPOINT_ID` und `VERTEX_ACCESS_TOKEN` gesetzt werden. Der Adapter ruft dann den Endpoint per `:predict` auf.

## Tests

```powershell
cd backend
python -m pytest
```

Mit `uv`:

```powershell
cd backend
$env:UV_CACHE_DIR=".uv-cache"
$env:UV_PYTHON_INSTALL_DIR=".uv-python"
uv run python -m pytest
```

Die Tests importieren die Demo-CSVs in eine lokale temporaere SQLite-Datei unter `backend/tests/.tmp/` und pruefen Import, Navigation und Chart-Serien.

Hinweis:

- `python backend/tests/test_chart.py` oder `uv run python tests/test_chart.py` laeuft jetzt ebenfalls ohne `ModuleNotFoundError: app`.
- Fuer echte Testlaeufe trotzdem `python -m pytest` oder `uv run python -m pytest` verwenden.

