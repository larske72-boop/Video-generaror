# ⚽ Football Shorts Generator

Maak automatisch virale voetbal YouTube Shorts met AI — vergelijkbaar met kanalen zoals [@nanifoty](https://youtube.com/@nanifoty).

## Wat genereert het?

| Template | Beschrijving |
|---|---|
| `goal_celebration` | Doelpunt vieringen in slow motion met flash |
| `skill_move` | Technische vaardigheden (elastico, rainbow, etc.) |
| `match_highlights` | Wedstrijd hoogtepunten compilatie |
| `player_spotlight` | Spotlight video van een specifieke speler |
| `save_of_the_day` | Spectaculaire keepersreddingen |
| `top_skills` | Top 5/10 skills compilatie |

**Output:** 1080×1920 MP4 (9:16) klaar voor YouTube Shorts, max 59 seconden.

---

## Installatie

```bash
# 1. Clone het project
git clone <repo-url>
cd Video-generaror

# 2. Installeer dependencies
pip install -r requirements.txt

# 3. Stel je Higgsfield API key in
cp .env.example .env
# Bewerk .env en vul je HIGGSFIELD_API_KEY in
```

Je hebt een **Higgsfield API key** nodig: maak een account aan op [higgsfield.ai](https://higgsfield.ai).

---

## Gebruik

### Enkelvoudige short genereren

```bash
# Basis — doelpunt viering
python main.py generate --template goal_celebration

# Met spelersnaam en club
python main.py generate --template goal_celebration --player "Messi" --club "Inter Miami"

# Skill move van Ronaldo
python main.py generate --template skill_move --player "Ronaldo" --club "Al-Nassr"

# Eigen prompt
python main.py generate --template skill_move --prompt "Neymar rainbow flick over two defenders, slow motion"

# Keeper van de dag
python main.py generate --template save_of_the_day --player "De Gea"
```

### Batch generatie

```bash
# 5 shorts van verschillende spelers
python main.py batch --template goal_celebration --count 5 \
  --players "Messi,Ronaldo,Mbappe,Haaland,Vinicius"
```

### Alle templates bekijken

```bash
python main.py list-templates
```

### Credit saldo controleren

```bash
python main.py check-balance
```

---

## Configuratie

Pas `config.yaml` aan voor eigen instellingen:

```yaml
branding:
  channel_name: "JOUW KANAAL"  # Watermark op video's

higgsfield:
  default_model: "kling3_0"    # AI video model
  clip_duration: 5             # Seconden per clip

output:
  max_duration: 59             # Max duur YouTube Short
  fps: 30
```

---

## Hoe het werkt

```
Jij kiest template + speler
        ↓
AI genereert voetbal clips (Higgsfield kling3_0)
        ↓
Effecten: slow motion, zoom, flash
        ↓
Overlays: spelersnaam, titel, watermark
        ↓
Clips samenvoegen + fade overgangen
        ↓
Export: 1080×1920 MP4 + thumbnail JPG
```

---

## Tips voor virale Shorts (nanifoty-stijl)

1. **Gebruik echte spelersnamen** in de prompt voor betere resultaten
2. **goal_celebration + slow_motion** werkt het beste voor engagement
3. **Genereer 3-5 clips** per short voor de juiste lengte (30-45s)
4. Upload op tijden dat je doelgroep online is (avond, weekend)
5. Gebruik de gegenereerde thumbnail — hij is al geoptimaliseerd voor clicks

---

## Bestandsstructuur

```
Video-generaror/
├── main.py              # CLI entry point
├── config.yaml          # Configuratie
├── requirements.txt
├── .env                 # Jouw API keys (niet in git)
├── src/
│   ├── generator.py     # Hoofd pipeline
│   ├── higgsfield_client.py  # Higgsfield REST API
│   ├── video_editor.py  # ffmpeg/MoviePy bewerking
│   └── prompts.py       # AI prompt templates
└── output/              # Gegenereerde videos
```
