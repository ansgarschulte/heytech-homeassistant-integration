# ✅ Verbindungstest

## Home Assistant ist jetzt erreichbar!

**URL:** http://localhost:8123

## Port-Mapping gefixt

Das Problem war:
- `network_mode: host` funktioniert nur auf Linux
- Auf macOS/Windows müssen Ports explizit gemappt werden

Jetzt verwendet docker-compose.yml:
```yaml
ports:
  - "8123:8123"
```

## Testen

```bash
# 1. Container läuft?
docker ps | grep homeassistant

# 2. Ports gemappt?
docker port homeassistant-heytech-test

# 3. Erreichbar?
curl -I http://localhost:8123/
# Sollte HTTP/1.1 302 zurückgeben

# 4. Im Browser öffnen
open http://localhost:8123
```

## Erste Schritte

1. Öffne http://localhost:8123
2. Erstelle einen Admin-Account
3. Gehe zu Settings → Devices & Services
4. Klicke auf "Add Integration"
5. Suche nach "Heytech"
6. Gib deine Controller-IP ein

Fertig! 🎉
