from pathlib import Path
import re, threading, uuid
from flask import Flask, jsonify, render_template, request, send_from_directory
import yt_dlp
BASE_DIR=Path(__file__).parent
DOWNLOAD_DIR=BASE_DIR/'downloads'; DOWNLOAD_DIR.mkdir(exist_ok=True)
app=Flask(__name__); jobs={}; URL_RE=re.compile(r'^https?://',re.I)
def platform_for(url):
    host=url.lower().split('/')[2] if '/' in url else ''
    if 'youtube.com' in host or 'youtu.be' in host:return 'YouTube'
    if 'instagram.com' in host:return 'Instagram'
    if 'facebook.com' in host or 'fb.watch' in host:return 'Facebook'
    if 'tiktok.com' in host:return 'TikTok'
    if 'twitter.com' in host or 'x.com' in host:return 'X / Twitter'
    return 'Other supported site'
def hook(job_id):
    def progress(data):
        if data.get('status')=='downloading': jobs[job_id]['progress']=data.get('_percent_str','0%').strip()
        elif data.get('status')=='finished': jobs[job_id]['progress']='100%'
    return progress
def run_download(job_id,url,kind,quality):
    jobs[job_id]['status']='downloading'; output=str(DOWNLOAD_DIR/f'{job_id}.%(ext)s')
    options={'format':'bestaudio/best' if kind=='mp3' else 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best','outtmpl':output,'noplaylist':True,'quiet':True,'no_warnings':True,'progress_hooks':[hook(job_id)],'postprocessors':[{'key':'FFmpegExtractAudio','preferredcodec':'mp3','preferredquality':quality}] if kind=='mp3' else [],'merge_output_format':'mp4' if kind=='mp4' else None}
    try:
        with yt_dlp.YoutubeDL(options) as downloader: downloader.download([url])
        files=list(DOWNLOAD_DIR.glob(f'{job_id}.*'))
        if not files: raise RuntimeError('The media file was not created')
        jobs[job_id].update(status='complete',progress='100%',filename=files[0].name)
    except Exception as exc: jobs[job_id].update(status='error',error=str(exc))
@app.get('/')
def home(): return render_template('index.html')
@app.get('/manifest.webmanifest')
def manifest(): return jsonify({'name':'Droply Media Downloader','short_name':'Droply','start_url':'/','display':'standalone','background_color':'#090b12','theme_color':'#090b12'})
@app.get('/service-worker.js')
def service_worker(): return "const CACHE='droply-v1';self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(['/']))));self.addEventListener('fetch',e=>e.respondWith(caches.match(e.request).then(r=>r||fetch(e.request))));",200,{'Content-Type':'application/javascript'}
@app.post('/api/download')
def create_download():
    data=request.get_json(silent=True) or {}; url=str(data.get('url','')).strip(); kind=data.get('format','mp4'); quality=data.get('quality','192')
    if not URL_RE.match(url): return jsonify(error='Enter a valid public URL beginning with http:// or https://'),400
    if kind not in {'mp3','mp4'}: return jsonify(error='Choose MP3 or MP4'),400
    job_id=uuid.uuid4().hex; jobs[job_id]={'status':'queued','progress':'0%','platform':platform_for(url)}
    threading.Thread(target=run_download,args=(job_id,url,kind,quality),daemon=True).start(); return jsonify(id=job_id,platform=jobs[job_id]['platform'])
@app.get('/api/download/<job_id>')
def download_status(job_id):
    job=jobs.get(job_id)
    if not job:return jsonify(error='Download not found'),404
    result=dict(job)
    if job.get('status')=='complete':result['download_url']=f"/files/{job['filename']}"
    return jsonify(result)
@app.get('/files/<path:filename>')
def files(filename): return send_from_directory(DOWNLOAD_DIR,filename,as_attachment=True)
if __name__=='__main__': app.run(host='0.0.0.0',port=5000)
