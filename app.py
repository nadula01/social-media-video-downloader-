```python
import os
import uuid
from urllib.parse import urlparse

from flask import (
    Flask,
    jsonify,
    request,
    send_from_directory,
    Response,
    stream_with_context
)

from flask_cors import CORS
import yt_dlp


app = Flask(__name__)
CORS(app)

TEMP_DIR = "/tmp"


# ---------------------------
# Helpers
# ---------------------------

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def get_info_options():
    return {
        "format": "best",
        "nocheckcertificate": True,
        "geo_bypass": True,
        "quiet": True
    }


def get_download_options(output_path):
    return {
        "format": "best",
        "outtmpl": output_path,
        "nocheckcertificate": True,
        "geo_bypass": True,
        "quiet": True
    }


def cleanup_file(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


# ---------------------------
# Routes
# ---------------------------

@app.route("/")
def home():
    return send_from_directory(".", "index.html")


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "service": "video-api"
    })


@app.route("/api/info", methods=["POST"])
def get_video_info():

    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "error": "No request body provided"
        }), 400

    url = data.get("url")

    if not url:
        return jsonify({
            "success": False,
            "error": "URL is required"
        }), 400

    if not is_valid_url(url):
        return jsonify({
            "success": False,
            "error": "Invalid URL"
        }), 400

    try:

        with yt_dlp.YoutubeDL(get_info_options()) as ydl:
            info = ydl.extract_info(url, download=False)

        return jsonify({
            "success": True,
            "title": info.get("title", "Unknown Title"),
            "thumbnail": info.get("thumbnail", ""),
            "duration": info.get("duration", 0)
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/download")
def download_video():

    url = request.args.get("url")

    if not url:
        return jsonify({
            "success": False,
            "error": "URL is required"
        }), 400

    if not is_valid_url(url):
        return jsonify({
            "success": False,
            "error": "Invalid URL"
        }), 400

    filename = f"{uuid.uuid4()}.mp4"

    output_path = (
        os.path.join(TEMP_DIR, filename)
        if os.path.exists(TEMP_DIR)
        else filename
    )

    try:

        with yt_dlp.YoutubeDL(
            get_download_options(output_path)
        ) as ydl:
            ydl.download([url])

        if not os.path.exists(output_path):

            return jsonify({
                "success": False,
                "error": "File not created"
            }), 500

        def generate():

            with open(output_path, "rb") as file:

                while True:

                    chunk = file.read(8192)

                    if not chunk:
                        break

                    yield chunk

            cleanup_file(output_path)

        return Response(
            stream_with_context(generate()),
            content_type="video/mp4",
            headers={
                "Content-Disposition":
                "attachment; filename=video.mp4"
            }
        )

    except Exception as e:

        cleanup_file(output_path)

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ---------------------------
# Main
# ---------------------------

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
```
