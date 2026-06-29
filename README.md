# ⚽ Mundial sin spoiler

Ver los resúmenes del Mundial del canal **DSports** sin spoilearte: no muestra el nombre, la miniatura ni el marcador hasta que le das play.

- **Página:** `index.html` — lista los partidos como "Equipo vs Equipo" (sin resultado) y los reproduce tapando título, miniatura y videos sugeridos.
- **`matches.json`** — lista de resúmenes detectados (id de YouTube + equipos + fecha). La página la lee del mismo origen.
- **`scripts/build.py`** — scrapea el canal y actualiza `matches.json` (sin borrar histórico).
- **GitHub Action** (`.github/workflows/update.yml`) — corre el script cada 2 horas para mantener la lista al día.

Hecho para uso personal.
