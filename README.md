# ⚽ Football Shorts Generator

Maak automatisch virale voetbal YouTube Shorts — zonder externe AI-API.  
Geef lokale videobestanden of YouTube-links op, en de generator doet de rest.

**Output:** 1080×1920 MP4 (9:16) + thumbnail, klaar voor YouTube Shorts.

---

## Installatie

```bash
# Dependencies installeren
pip install -r requirements.txt

# ffmpeg is ook vereist (voor video verwerking):
# Ubuntu/Debian:  sudo apt install ffmpeg
# macOS:          brew install ffmpeg
# Windows:        https://ffmpeg.org/download.html
```

---

## Gebruik

### Van lokale bestanden

```bash
python main.py generate clip1.mp4 clip2.mp4 \
  --template goal_celebration \
  --player "Messi" \
  --club "Inter Miami" \
  --music assets/music/hype.mp3
```

### Van YouTube-URLs (automatisch downloaden)

```bash
python main.py generate "https://youtu.be/..." \
  --template skill_move \
  --player "Neymar" \
  --club "Al-Hilal"
```

### Combinatie van lokaal + URL

```bash
python main.py generate clip_intro.mp4 "https://youtu.be/..." clip_outro.mp4 \
  --template match_highlights \
  --team-a "PSG" --score-a 3 \
  --team-b "Real Madrid" --score-b 1
```

### Batch — meerdere shorts van een URL-lijst

```bash
# urls.txt: één YouTube-URL per regel, # = commentaar
python main.py batch urls_example.txt \
  --template goal_celebration \
  --clips-per-short 3 \
  --player "Haaland" \
  --music assets/music/epic.mp3
```

### Alle templates bekijken

```bash
python main.py list-templates
```

---

## Templates

| Template | Beschrijving | Slow-Mo | Flash |
|---|---|:---:|:---:|
| `goal_celebration` | Doelpunt vieringen | ✓ | ✓ |
| `skill_move` | Skills (elastico, rainbow, etc.) | ✓ | |
| `match_highlights` | Wedstrijdcompilatie + scorebord | | |
| `player_spotlight` | Spotlight van één speler | ✓ | |
| `save_of_the_day` | Keepersreddingen | ✓ | ✓ |
| `top_skills` | Skills compilatie | | |

---

## Muziek toevoegen

Zet royalty-free MP3/WAV-bestanden in `assets/music/` en geef het pad mee via `--music`.

Gratis bronnen:
- [YouTube Audio Library](https://studio.youtube.com/channel/music)
- [Pixabay Music](https://pixabay.com/music/)
- [Free Music Archive](https://freemusicarchive.org/)

---

## Configuratie

Pas `config.yaml` aan voor eigen branding en instellingen:

```yaml
branding:
  channel_name: "JOUW KANAAL"     # Watermark tekst op elke clip

text:
  accent_color: "#FFD700"         # Goud — pas aan naar je huisstijl

effects:
  slow_motion_factor: 0.5         # 0.5 = halve snelheid
  zoom_scale: 1.12                # Zoom-in factor (Ken-Burns)
```

---

## Bestandsstructuur

```
Video-generaror/
├── main.py                  ← CLI
├── config.yaml              ← Instellingen
├── requirements.txt
├── urls_example.txt         ← Voorbeeld URL-batch bestand
├── src/
│   ├── generator.py         ← Hoofd pipeline
│   ├── downloader.py        ← yt-dlp clip downloader
│   ├── video_editor.py      ← MoviePy effecten + export
│   └── overlays.py          ← PIL tekst / branding overlays
├── assets/
│   └── music/               ← Zet hier jouw muziekbestanden
└── output/                  ← Gegenereerde videos komen hier
```

---

## Hoe het werkt

```
Jij geeft clips of YouTube-links op
           ↓
yt-dlp downloadt de clips (indien URL)
           ↓
Clips worden bewerkt:
  • 9:16 crop (cover mode)
  • Slow motion (indien actief)
  • Ken-Burns zoom
  • Flash effect bij doelpunten
           ↓
Overlays worden toegevoegd:
  • Spelersnaam + club balk
  • Titel + emoji
  • Kanaal watermark
  • Score badge (bij match_highlights)
           ↓
Clips samenvoegen met fades + kanaalintro
           ↓
Achtergrondmuziek mixen
           ↓
Export: 1080×1920 MP4 + thumbnail JPG
```
