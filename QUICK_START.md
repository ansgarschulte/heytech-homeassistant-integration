# 🚀 Quick Start

## Ja, dein Code ist live gemountet! ✅

Jede Änderung in `custom_components/heytech/` ist sofort im Container.

## 1. Start Test Environment

```bash
docker-compose up -d
```

Warte ~30 Sekunden, dann öffne: **http://localhost:8123**

⚠️ **Beim ersten Start**: Erstelle einen Admin-Account!

## 2. Code ändern

```bash
# Bearbeite beliebige Datei
vim custom_components/heytech/api.py
```

## 3. Reload (3 Optionen)

### A) Mit Script (Empfohlen) ⚡
```bash
./dev-reload.sh
# Wähle Option 1
```

### B) Manuell Quick Reload
```bash
docker exec homeassistant-heytech-test ha core reload
```

### C) Full Restart (bei Problemen)
```bash
docker-compose restart
```

## 4. Logs checken

```bash
docker-compose logs -f homeassistant | grep heytech
```

## Das war's! 🎉

**Workflow:**
1. Code ändern
2. `./dev-reload.sh` ausführen
3. In http://localhost:8123 testen
4. Wiederholen

## Wichtige Dateien

- `custom_components/heytech/api.py` - Haupt-API
- `custom_components/heytech/cover.py` - Rolladen
- `custom_components/heytech/sensor.py` - Sensoren
- `custom_components/heytech/scene.py` - Szenarien

## Hilfe

- **Fehler?** → `docker-compose logs homeassistant | grep error`
- **Nicht sichtbar?** → `docker-compose restart`
- **Details?** → Siehe `DEVELOPMENT.md`

**Los geht's!** 💪
