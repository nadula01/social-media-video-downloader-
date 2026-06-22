import os
import uuid
from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
from flask_cors import CORS
import yt_dlp

app = Flask(__name__)
CORS(app)

# සර්වර් බ්ලොක් වැළැක්වීමට නවතම බයිපාස් සැකසුම්
YDL_OPTS_BASE = {
    'format': 'best',
    'nocheckcertificate': True,
    'geo_bypass': True,
    'quiet': True,
    'extractor_args': {
        'youtube': {
            'player_client': ['ios', 'web_embedded'],
            'skip': ['dash', 'hls']
        },
        'tiktok': {
            'app_version': '31.5.3',
            'manifest_version': '20231016'
        }
    },
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.instagram.com/', # සමහර විට රෙෆරර් එක වෙනස් කිරීමෙන් බ්ලොක් එක ලිහේ
    }
}

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api/info', methods=['POST'])
def get_info():
    data = request.json
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
        
    url = data.get('url')
    if not url:
        return jsonify({'success': False, 'error': 'URL is required'}), 400
        
    try:
        with yt_dlp.YoutubeDL(YDL_OPTS_BASE) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({
                'success': True,
                'title': info.get('title', 'Video'),
                'thumbnail': info.get('thumbnail', ''),
                'duration': info.get('duration', 0)
            })
    except Exception as e:
        # මෙතන 'success': False දැමීම අත්‍යවශ්‍යයි (index.html එකේ d.success බලන නිසා)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/download', methods=['GET'])
def download_video():
    url = request.args.get('url')
    if not url:
        return "URL is required", 400
        
    filename = f"{uuid.uuid4()}.mp4"
    outtmpl = os.path.join('/tmp', filename) if os.path.exists('/tmp') else filename
    
    ydl_opts = YDL_OPTS_BASE.copy()
    ydl_opts['outtmpl'] = outtmpl
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        if os.path.exists(outtmpl):
            def generate():
                with open(outtmpl, 'rb') as f:
                    while True:
                        chunk = f.read(8192)
                        if not chunk:
                            break
                        yield chunk
                try:
                    os.remove(outtmpl)
                except:
                    pass
                    
            return Response(
                stream_with_context(generate()),
                content_type='video/mp4',
                headers={"Content-Disposition": "attachment; filename=video.mp4"}
            )
        else:
            return "Download failed on server", 500
            
    except Exception as e:
        if os.path.exists(outtmpl):
            try: os.remove(outtmpl)
            except: pass
        return str(e), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
