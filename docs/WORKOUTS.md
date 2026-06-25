# Workout-Format und Parametrierung

## Empfehlung: JSON speichern, Tabelle bearbeiten, Graph zur Vorschau

| Zweck | Format | Warum |
|-------|--------|-------|
| **Speichern / Versionieren** | JSON in `workouts/` | lesbar, diff-freundlich, portierbar |
| **Bearbeiten** | Tabelle + Zeilen-Editor in NiceGUI | praezise Werte (Sekunden, Watt) |
| **Verstehen / Pruefen** | ECharts-Treppenprofil | sofort sichtbar, ob das Profil stimmt |

Ein reiner Graph-Editor waere fuer Intervalle unhandlich (exakte 30 s / 200 W).
Eine reine Tabelle ohne Graph waere schwer zu pruefen. **Beides zusammen** ist der Standard
in Trainings-Apps.

## JSON-Schema

```json
{
  "name": "4x30 Intervall",
  "description": "Kurzbeschreibung",
  "steps": [
    {"duration_s": 120, "target_power_w": 100, "label": "Aufwaermen"},
    {"duration_s": 30, "target_power_w": 200, "label": "Intervall 1"}
  ]
}
```

## Ordner

- `workouts/*.json` — Vorlagen (im Git)
- `workouts/user/*.json` — deine eigenen Workouts (nicht im Git)

## In der App

1. Workout aus Dropdown waehlen
2. Profil-Graph und Tabelle pruefen
3. Schritte im Editor anpassen (Dauer, Watt, Label)
4. **Speichern** (ueberschreibt Vorlage nur bei `user/…`) oder **Speichern unter …**
5. **Workout starten** — `WorkoutRunner` setzt ERG-Watt pro Schritt

## CLI (ohne GUI)

```powershell
python -m core.ftms scan
python -m core.ftms erg --address AA:BB:CC:DD:EE:FF --watts 150 --duration 60
```
