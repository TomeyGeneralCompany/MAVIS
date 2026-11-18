"""Activation page shown instead of the production dashboard until licensed."""
HTML = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>MAVIS Activation</title>
<style>body{background:#f8f8f8;color:#183536;font:16px system-ui,sans-serif;max-width:650px;margin:8vh auto;padding:24px}
h1{color:#00a9b4}code{display:block;padding:16px;background:white;border:1px solid #aaa;overflow-wrap:anywhere}
textarea{width:100%;height:150px;box-sizing:border-box}button{background:#00a9b4;color:white;border:0;padding:12px 20px;cursor:pointer}</style>
</head><body><h1>MAVIS · Activate this computer</h1>
<p>Give this device code to the MAVIS license issuer. Paste the signed activation they return.</p>
<code id="device">__DEVICE__</code>
<p><label for="license">Signed activation (JSON)</label></p>
<textarea id="license" spellcheck="false" autocomplete="off"></textarea>
<p><button id="activate">Activate MAVIS</button></p><p id="message" role="status"></p>
<script>const token='__STUDIO_TOKEN__';
document.getElementById('activate').addEventListener('click',async()=>{
const message=document.getElementById('message');message.textContent='Verifying…';
try {
const response=await fetch('/activation',{method:'POST',
headers:{'X-Studio-Token':token,'Content-Type':'application/json'},
body:JSON.stringify({license:document.getElementById('license').value})});
const data=await response.json();
if(!response.ok)throw Error(data.error||'Activation failed');
location.reload();
} catch(error){message.textContent=error.message}
});</script></body></html>"""
