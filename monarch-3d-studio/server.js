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
  if(url==='/') url='/index.html';
  let filePath = path.join(ROOT, url);
  // prevent traversal
  if(!filePath.startsWith(ROOT)){ res.writeHead(403); return res.end('Forbidden'); }

  fs.readFile(filePath, (err,data)=>{
    if(err){
      res.writeHead(404, {'Content-Type':'text/plain'});
      return res.end('Not found: '+url);
    }
    const ext = path.extname(filePath).toLowerCase();
    res.writeHead(200, {'Content-Type': MIME[ext]||'application/octet-stream', 'Cache-Control':'no-cache'});
    res.end(data);
  });
});

server.listen(PORT, '0.0.0.0', ()=>{
  console.log(`Monarch 3D Studio running on http://0.0.0.0:${PORT}`);
  console.log(`Preview: https://${PORT}-<sandbox>.e2b.app`);
});
