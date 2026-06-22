import os
import uuid
import threading
import time
from flask import Flask, request, jsonify, Response, send_from_directory, stream_with_context
from flask_cors import CORS
import yt_dlp

# සර්වර් එකේ නිවැරදිම Path එක සොයාගැනීම (404 Error එක නැති කිරීමට)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_FOLDER = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
CORS(app)

# -----------------------------
# GLOBAL PROGRESS STORE
# -----------------------------
progress_data = {
    "percent": 0,
    "speed": "0 KB/s",
    "eta": "0s"
}

# YouTube සහ TikTok බ්ලොක් වැළැක්වීමට විශේෂ උපක්‍රම
YDL_OPTS_BASE = {
    'nocheckcertificate': True,
    'geo_bypass': True,
    'quiet': True,
    'extractor_args': {
        'youtube': {
            'player_client': ['ios', 'android', 'web_embedded'],
            'skip': ['dash', 'hls']
        }
    },
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
}

# -----------------------------
# FRONTEND ROUTE (අතුරුදන් වුණු සයිට් එක ආපහු ලබා ගැනීමට)
# -----------------------------
@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')

# -----------------------------
# INFO API
# -----------------------------
@app.route("/api/info", methods=["POST"])
def info():
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400
        
    url = data.get("url")
    if not url:
        return jsonify({"error": "URL is required"}), 400

    try:
        ydl_opts = YDL_OPTS_BASE.copy()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=False)

        formats = []
        for f in info_dict.get("formats", []):
            if f.get("vcodec") == "none" and f.get("acodec") == "none":
                continue

            size = f.get("filesize") or f.get("filesize_approx") or 0
            size_mb = round(size / (1024 * 1024), 2) if size else 0

            formats.append({
                "id": f.get("format_id"),
                "quality": f.get("format_note") or f.get("height") or "audio",
                "ext": f.get("ext"),
                "type": "audio" if f.get("vcodec") == "none" else "video",
                "size": f"{size_mb} MB"
            })

        return jsonify({
            "title": info_dict.get("title"),
            "thumbnail": info_dict.get("thumbnail"),
            "channel": info_dict.get("uploader"),
            "duration": info_dict.get("duration"),
            "formats": formats
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -----------------------------
# PROGRESS HOOK
# -----------------------------
def progress_hook(d):
    global progress_data
    if d["status"] == "downloading":
        downloaded = d.get("downloaded_bytes", 0)
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 1
        percent = int(downloaded / total * 100)

        speed = d.get("speed") or 0
        speed_mb = f"{round(speed / 1024 / 1024, 2)} MB/s" if speed else "0 MB/s"
        eta = d.get("eta") or 0

        progress_data["percent"] = percent
        progress_data["speed"] = speed_mb
        progress_data["eta"] = f"{eta}s"

    if d["status"] == "finished":
        progress_data["percent"] = 100

# -----------------------------
# DOWNLOAD API
# -----------------------------
@app.route("/api/download")
def download():
    global progress_data
    # හැම ඩවුන්ලෝඩ් එකක්ම පටන් ගද්දීම progress එක 0 කරනවා
    progress_data = {"percent": 0, "speed": "0 KB/s", "eta": "0s"}

    url = request.args.get("url")
    format_id = request.args.get("format")

    if not url or not format_id:
        return "Missing parameters", 400

    filename = str(uuid.uuid4())
    # Render එකේ තාවකාලික ඉඩ (tmp) පාවිච්චි කිරීම
    outtmpl = os.path.join('/tmp', filename + ".%(ext)s") if os.path.exists('/tmp') else os.path.join(DOWNLOAD_FOLDER, filename + ".%(ext)s")

    ydl_opts = YDL_OPTS_BASE.copy()
    ydl_opts.update({
        "format": format_id,
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "progress_hooks": [progress_hook],
    })

    try:
        # Thread/Sleep නැතුව සර්වර් එක ඇතුළට කෙලින්ම Download කරගැනීම
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # බාගත වුණු ෆයිල් එක නිවැරදිව සොයාගැනීම
        search_dir = '/tmp' if os.path.exists('/tmp') else DOWNLOAD_FOLDER
        file_path = None
        for f in os.listdir(search_dir):
            if f.startswith(filename):
                file_path = os.path.join(search_dir, f)
                break

        if not file_path or not os.path.exists(file_path):
            return "File download failed on server", 500

        def generate():
            with open(file_path, "rb") as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    yield chunk
            try:
                os.remove(file_path)
            except:
                pass

        return Response(
            stream_with_context(generate()),
            mimetype="video/mp4",
            headers={"Content-Disposition": "attachment; filename=video.mp4"}
        )

    except Exception as e:
        return str(e), 500

# -----------------------------
# PROGRESS STREAM (SSE)
# -----------------------------
@app.route("/progress")
def progress():
    def event_stream():
        import json
        while True:
            time.sleep(1)
            # SSE එකට හරියටම JSON string එකක් විදිහට දත්ත යැවීම
            yield f"data: {json.dumps(progress_data)}\n\n"
    return Response(event_stream(), mimetype="text/event-stream")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
