import os
import uuid
import threading
import time
from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# -----------------------------
# GLOBAL PROGRESS STORE
# -----------------------------
progress_data = {
    "percent": 0,
    "speed": "0 KB/s",
    "eta": "0s"
}

# -----------------------------
# INFO API
# -----------------------------
@app.route("/api/info", methods=["POST"])
def info():
    data = request.json
    url = data.get("url")

    if not url:
        return jsonify({"error": "URL is required"}), 400

    try:
        ydl_opts = {
            "quiet": True,
            "nocheckcertificate": True,
            "geo_bypass": True
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        formats = []

        for f in info.get("formats", []):

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
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "channel": info.get("uploader"),
            "duration": info.get("duration"),
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

    url = request.args.get("url")
    format_id = request.args.get("format")

    if not url or not format_id:
        return "Missing parameters", 400

    filename = str(uuid.uuid4())
    outtmpl = os.path.join(DOWNLOAD_FOLDER, filename + ".%(ext)s")

    ydl_opts = {
        "format": format_id,
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "progress_hooks": [progress_hook],
        "quiet": True
    }

    def run_download():
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            print("Download error:", e)

    threading.Thread(target=run_download).start()
    time.sleep(2)

    file_path = None
    for f in os.listdir(DOWNLOAD_FOLDER):
        if f.startswith(filename):
            file_path = os.path.join(DOWNLOAD_FOLDER, f)
            break

    if not file_path:
        return "File not found", 500

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
        generate(),
        mimetype="video/mp4",
        headers={
            "Content-Disposition": "attachment; filename=video.mp4"
        }
    )


# -----------------------------
# PROGRESS STREAM (SSE)
# -----------------------------
@app.route("/progress")
def progress():

    def event_stream():
        while True:
            time.sleep(1)
            yield f"data: {progress_data}\n\n"

    return Response(event_stream(), mimetype="text/event-stream")


# -----------------------------
# RENDER ENTRY POINT
# -----------------------------
# IMPORTANT: Render uses gunicorn, so this won't run there
# but kept for local testing
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
