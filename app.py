import os
import uuid
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import yt_dlp
import re

app = Flask(__name__)
CORS(app)

DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/info', methods=['POST'])
def get_video_info():
    data = request.json
    video_url = data.get('url')
    try:
        ydl_opts = {'quiet': True, 'skip_download': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
            return jsonify({
                'success': True,
                'title': info.get('title', 'video'),
                'thumbnail': info.get('thumbnail', '')
            })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/download', methods=['GET'])
def download_video():
    video_url = request.args.get('url')
    quality = request.args.get('quality', '')
    
    # Check if requested format is audio
    is_audio = quality == 'Audio'
    ext = 'mp3' if is_audio else 'mp4'
    
    with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
        info = ydl.extract_info(video_url, download=False)
        title = re.sub(r'[\\/*?:"<>|]', "", info.get('title', 'video'))
        unique_id = uuid.uuid4().hex[:6]
        filename = f"{title}_{quality}_{unique_id}.{ext}"
        filepath = os.path.join(DOWNLOAD_FOLDER, filename)

    
    if is_audio:
        ydl_opts = {
            'outtmpl': os.path.join(DOWNLOAD_FOLDER, f"{title}_{quality}_{unique_id}.%(ext)s"),
            'quiet': True,
            'format': 'bestaudio/best',
        }
    else:
        format_map = {
            '1080p': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '720p': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '480p': 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '360p': 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '240p': 'bestvideo[height<=240][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            '144p': 'bestvideo[height<=144][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        }
        selected_format = format_map.get(quality, 'best[ext=mp4]/best')
        ydl_opts = {
            'outtmpl': filepath,
            'quiet': True,
            'format': selected_format,
            'merge_output_format': 'mp4'
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            download_info = ydl.extract_info(video_url, download=True)
           
            if is_audio:
                actual_ext = download_info.get('ext', 'mp3')
                actual_filename = f"{title}_{quality}_{unique_id}.{actual_ext}"
                filepath = os.path.join(DOWNLOAD_FOLDER, actual_filename)
                filename = actual_filename

        return send_file(filepath, as_attachment=True, download_name=filename)
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)