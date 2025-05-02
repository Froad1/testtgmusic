# Flask-сервер для пошуку та надсилання треків у Telegram через SoundCloud API

from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
import subprocess


app = Flask(__name__)
CORS(app)

TELEGRAM_BOT_TOKEN = "6516656222:AAGuWlfNF4VI4CWGHwFhYKqs3UeHP0cev4U"
TELEGRAM_CHAT_ID = "710609410"
SOUNDCLOUD_CLIENT_ID = "EjkRJG0BLNEZquRiPZYdNtJdyGtTuHdp"
DOWNLOAD_DIR = "downloads"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


@app.route("/api/search")
def search():
    query = request.args.get("q")
    if not query:
        return jsonify({"error": "No query provided"}), 400

    try:
        url = f"https://api-v2.soundcloud.com/search/tracks?q={requests.utils.quote(query)}&client_id={SOUNDCLOUD_CLIENT_ID}&limit=10"
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        results = []
        for track in data.get("collection", []):
            results.append({
                "id": track["id"],
                "title": track["title"],
                "artist": track["user"]["username"],
                "thumbnail": (track["artwork_url"] or "").replace("large", "t300x300"),
                "permalink_url": track["permalink_url"]
            })

        return jsonify(results)

    except Exception as e:
        print("Search error:", e)
        return jsonify({"error": "Search failed"}), 500


@app.route("/api/send", methods=["POST"])
def send():
    data = request.get_json()
    permalink_url = data.get("permalink_url")
    if not permalink_url:
        return jsonify({"error": "No permalink_url provided"}), 400

    # Очистити попередні треки
    for f in os.listdir(DOWNLOAD_DIR):
        os.remove(os.path.join(DOWNLOAD_DIR, f))

    # Завантажити аудіо з SoundCloud
    try:
        print("Downloading track:", permalink_url)
        result = subprocess.run([
            "yt-dlp",
            "--extract-audio",
            "--audio-format", "mp3",
            permalink_url,
            "-o", f"{DOWNLOAD_DIR}/%(title)s.%(ext)s"
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        print("Download finished")

        # Знайти MP3 файл
        audio_file = next((f for f in os.listdir(DOWNLOAD_DIR) if f.endswith(".mp3")), None)
        if not audio_file:
            return jsonify({"error": "MP3 not found"}), 500

        # Надіслати файл у Telegram
        with open(os.path.join(DOWNLOAD_DIR, audio_file), "rb") as f:
            response = requests.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendAudio",
                data={"chat_id": TELEGRAM_CHAT_ID},
                files={"audio": f}
            )

        if not response.ok:
            print("Telegram error:", response.text)
            return jsonify({"error": "Telegram failed", "details": response.text}), 500

        return jsonify({"success": True})

    except subprocess.CalledProcessError as e:
        print("Download error:", e.stderr.decode())
        return jsonify({"error": "Download failed", "details": e.stderr.decode()}), 500
    except Exception as e:
        return jsonify({"error": "Unexpected error", "details": str(e)}), 500


if __name__ == "__main__":
    app.run(port=3001, debug=True)
