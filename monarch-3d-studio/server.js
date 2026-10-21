const http = require('http');
const fs = require('fs');
const path = require('path');
const PORT = process.env.PORT || 3000;
const ROOT = __dirname;

const MIME = {
  '.html':'text/html', '.js':'text/javascript', '.css':'text/css',
  '.json':'application/json', '.png':'image/png', '.jpg':'image/jpeg',
  '.jpeg':'image/jpeg', '.mp4':'video/mp4', '.webm':'video/webm',
  '.glb':'model/gltf-binary', '.gltf':'model/gltf+json', '.wasm':'application/wasm'
};

const server = http.createServer((req,res)=>{
  // CORS for preview
  res.setHeader('Access-Control-Allow-Origin','*');
  res.setHeader('Access-Control-Allow-Methods','GET,POST,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers','*');
  // frame allow
  res.setHeader('X-Frame-Options','ALLOWALL');
  res.setHeader('Content-Security-Policy',"frame-ancestors *");
  if(req.method==='OPTIONS'){ res.writeHead(204); return res.end(); }

  let url = req.url.split('?')[0];
  if(url==='/') url='/film.html';
  let filePath = path.join(ROOT, url);
  // prevent traversal
  if(!filePath.startsWith(ROOT)){ res.writeHead(403); return res.end('Forbidden'); }

  const ext = path.extname(filePath).toLowerCase();
  const type = MIME[ext]||'application/octet-stream';

  fs.stat(filePath, (err, st)=>{
    if(err || !st.isFile()){
      res.writeHead(404, {'Content-Type':'text/plain'});
      return res.end('Not found: '+url);
    }
    // HTTP Range support so <video> can seek/scrub
    const range = req.headers.range;
    if(range && /^bytes=/.test(range)){
      const parts = range.replace(/bytes=/,'').split('-');
      const start = parseInt(parts[0],10) || 0;
      const end = parts[1] ? Math.min(parseInt(parts[1],10), st.size-1)
                           : st.size-1;
      if(start >= st.size || end < start){
        res.writeHead(416, {'Content-Range':`bytes */${st.size}`});
        return res.end();
      }
      res.writeHead(206, {
        'Content-Type': type,
        'Content-Length': end-start+1,
        'Content-Range': `bytes ${start}-${end}/${st.size}`,
        'Accept-Ranges': 'bytes',
        'Cache-Control': 'no-cache'
      });
      fs.createReadStream(filePath,{start,end}).pipe(res);
      return;
    }

    res.writeHead(200, {
      'Content-Type': type,
      'Content-Length': st.size,
      'Accept-Ranges': 'bytes',
      'Cache-Control': 'no-cache'
    });
    if(req.method==='HEAD') return res.end();
    fs.createReadStream(filePath).pipe(res);
  });
});

server.listen(PORT, '0.0.0.0', ()=>{
  console.log(`Monarch 3D Studio running on http://0.0.0.0:${PORT}`);
  console.log(`Preview: https://${PORT}-<sandbox>.e2b.app`);
});
