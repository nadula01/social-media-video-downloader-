import os
import uuid
from flask import Flask, request, jsonify, send_from_directory, Response, stream_with_context
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
    if not url:
        return "URL is required", 400
        
    # සර්වර් එක ඇතුළේ temporary ෆයිල් එකක් විදිහට download කිරීම
    filename = f"{uuid.uuid4()}.mp4"
    outtmpl = os.path.join('/tmp', filename) if os.path.exists('/tmp') else filename
    
    ydl_opts = {
        'format': 'best',
        'outtmpl': outtmpl,
        'nocheckcertificate': True,
        'geo_bypass': True,
        'quiet': True
    }
    
    try:
        # yt-dlp එකෙන්ම සර්වර් එක ඇතුළට වීඩියෝ එක මුලින්ම බාගත කිරීම
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
                # වීඩියෝ එක පරිශීලකයාට යවා ඉවර වූ සැණින් සර්වර් එකෙන් මකා දැමීම (Storage පිරෙන්නේ නැති වෙන්න)
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
