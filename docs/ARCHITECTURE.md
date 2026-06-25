# Fitness — Architektur

## Ziel

Schrittweise Steuerung eines **Wahoo KICKR CORE 2** über **FTMS** (Bluetooth LE).
Phase 1: PC-Prototyp mit Python und NiceGUI (analog KT-workspace).

## Schichten

```
+-----------------------------------------+
|  app_kickr/          NiceGUI (UI only)  |
|  -- Buttons, Labels, Timer, Port 8080   |
+------------------------+----------------+
                         | nutzt
+------------------------v----------------+
|  core/ftms/          Domänenlogik       |
|  -- FtmsClient, Parser, Opcodes         |
|  -- keine Abhaengigkeit von NiceGUI     |
+------------------------+----------------+
                         | nutzt
+------------------------v----------------+
|  bleak               BLE (Windows)      |
+-----------------------------------------+
```

**Regel:** Alles, was spaeter auf Android/iOS/tvOS portiert wird, gehoert in `core/`.
NiceGUI ist nur der **Phase-1-Adapter** fuer Desktop/Labor.

## Warum NiceGUI hier passt

| Kriterium | Bewertung |
|-----------|-----------|
| Bekannt aus KT-workspace | Gleiches Muster (`python -m app_*`, `ui.run`) |
| Live-Daten (Watt, Kadenz) | `ui.timer` + async BLE-Callbacks |
| Labor/Prototyp am PC | Ideal — kein separates Frontend-Build |
| Spaetere Mobile/TV-Apps | Core bleibt nutzbar; UI wird ersetzt |

NiceGUI ist **nicht** das Endprodukt fuer Apple TV oder Android, aber **architektonisch sauber**,
wenn der FTMS-Code davon getrennt bleibt.

## FTMS-Ablauf (KICKR)

1. BLE-Scan nach Service `0x1826`
2. Connect, Notifications auf Indoor Bike Data (`0x2AD2`)
3. Indications auf Control Point (`0x2AD9`)
4. `Request Control` -> `0x00`, Erfolg: `80 00 01`
5. `Start/Resume` -> `0x07`
6. `Set Target Power` -> `0x05` + Watt (ERG)

## Phasen

| Phase | Plattform | UI |
|-------|-----------|-----|
| 1 | PC (Windows) | NiceGUI + `core/ftms` |
| 2 | Android | Kotlin + portierte FTMS-Logik |
| 3 | iPad | Swift / CoreBluetooth |
| 4 | Apple TV | tvOS (eigenes Target) |

## Start Phase 1

```powershell
cd C:\_Git\Fitness
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app_kickr
```

Browser: `http://localhost:8080`
