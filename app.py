import os
from flask import Flask, request, jsonify, send_from_directory, redirect
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/info', methods=['POST'])
def get_info():
    data = request.json
    if not data:
        return jsonify({'error': 'No data provided'}), 400
        
    url = data.get('url')
    if not url:
        return jsonify({'error': 'URL is required'}), 400
        
    ydl_opts = {
        'format': 'best',
        'nocheckcertificate': True,
        'geo_bypass': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({
                'title': info.get('title', 'Video'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0)
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['GET'])
def download_video():
    url = request.args.get('url')
    quality = request.args.get('quality', '')
    
    if not url:
        return "URL is required", 400
        
    ydl_opts = {
        'format': 'best',
        'nocheckcertificate': True,
        'geo_bypass': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        }
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            download_url = info.get('url')
            
            if not download_url and 'formats' in info:
                valid_formats = [f for f in info['formats'] if f.get('url')]
                if valid_formats:
                    download_url = valid_formats[-1].get('url')
            
            if download_url:
                return redirect(download_url)
            else:
                return "Could not extract download URL", 404
    except Exception as e:
        return str(e), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
