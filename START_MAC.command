#!/bin/bash
cd "$(dirname "$0")"
echo ""
echo " ============================================="
echo "  Football Shorts Generator - Opstarten..."
echo " ============================================="
echo ""

# Controleer Python
if ! command -v python3 &>/dev/null; then
    echo " [FOUT] Python niet gevonden!"
    echo " Download via: https://python.org"
    read -p "Druk op Enter om af te sluiten..."
    exit 1
fi

# Installeer dependencies
echo " Benodigde onderdelen installeren..."
pip3 install flask yt-dlp moviepy Pillow numpy imageio imageio-ffmpeg --quiet

# Toon lokaal IP-adres
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || hostname -I 2>/dev/null | awk '{print $1}')
echo ""
echo " App draait op: http://localhost:5000"
echo " iPhone (zelfde WiFi): http://$LOCAL_IP:5000"
echo ""

python3 app.py
