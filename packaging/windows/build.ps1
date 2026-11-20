$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '../..')
function Checked($program, $arguments) {
    & $program @arguments
    if ($LASTEXITCODE -ne 0) { throw "$program failed: $LASTEXITCODE" }
}
$app = Join-Path $PWD 'build/windows/app'
New-Item -ItemType Directory -Force $app | Out-Null
# Explicit allowlist: never package workspace data, credentials, or customer media.
$files = @('studio.html','local_studio.py','run_mavis.py','configure_media.py','windows_launcher.py','requirements.txt','.env.example')
foreach ($file in $files) { Copy-Item $file $app }
foreach ($dir in @('mavis','examples','voice-runtime')) { Copy-Item $dir $app -Recurse -Force }
Get-ChildItem $app -Directory -Filter __pycache__ -Recurse | Remove-Item -Recurse -Force
New-Item -ItemType Directory -Force "$app/packaging/windows" | Out-Null
Copy-Item packaging/provision.py "$app/packaging/"
Copy-Item packaging/windows/provision.py "$app/packaging/windows/"
Set-Content -Encoding ascii "$app/subscription.json" '{"required":false,"url":""}'
Invoke-WebRequest 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip' -OutFile build/windows/python.zip
Expand-Archive build/windows/python.zip "$app/python" -Force
# Vendor dependencies at build time; customers need no Python or pip installation.
Checked python @('-m','pip','install','--only-binary=:all:','--target',"$app/python/Lib/site-packages",'-r','requirements.txt')
Set-Content -Encoding ascii "$app/python/python312._pth" "python312.zip`n.`n..`nLib/site-packages`nimport site"
Checked python @('-c',"from PIL import Image; Image.open('packaging/icon.png').save(r'$app/mavis.ico',sizes=[(16,16),(32,32),(48,48),(128,128)])")
Checked git @('clone','--recurse-submodules','https://github.com/ServeurpersoCom/qwentts.cpp.git','build/windows/qwen')
Checked git @('-C','build/windows/qwen','checkout','2edb35f87b709a070b2d5379f77e5c52a1daa585')
Checked git @('-C','build/windows/qwen','submodule','update','--init','--recursive')
Checked cmake @('-S','build/windows/qwen','-B','build/windows/qwen/build','-A','x64','-DGGML_NATIVE=OFF','-DGGML_CUDA=OFF','-DGGML_VULKAN=OFF','-DBUILD_SHARED_LIBS=OFF')
Checked cmake @('--build','build/windows/qwen/build','--config','Release','--target','qwen-tts','-j','2')
New-Item -ItemType Directory -Force "$app/voice/source/build/Release" | Out-Null
Get-ChildItem build/windows/qwen/build -Recurse -File | Where-Object { $_.Extension -in '.exe','.dll' } | Copy-Item -Destination "$app/voice/source/build/Release"
Copy-Item build/windows/qwen/LICENSE "$app/voice/ENGINE-LICENSE.txt"
Invoke-WebRequest 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip' -OutFile build/windows/ffmpeg.zip
Expand-Archive build/windows/ffmpeg.zip build/windows/ffmpeg -Force
New-Item -ItemType Directory -Force "$app/tools" | Out-Null
Get-ChildItem build/windows/ffmpeg -Recurse -File | Where-Object { $_.Name -in 'ffmpeg.exe','ffprobe.exe','LICENSE.txt' } | Copy-Item -Destination "$app/tools"
# Verify the shipped interpreter imports the real sources and intact guards.
Checked "$app/python/python.exe" @('-c','import mavis, run_mavis, local_studio; from zoneinfo import ZoneInfo; ZoneInfo("America/Detroit")')
Checked "$app/tools/ffmpeg.exe" @('-version')
Checked "$app/voice/source/build/Release/qwen-tts.exe" @('--help')
$iscc = "${env:ProgramFiles(x86)}/Inno Setup 6/ISCC.exe"
Checked $iscc @('packaging/windows/MAVIS.iss')
Get-FileHash dist/MAVIS-Windows-Setup.exe -Algorithm SHA256 | ForEach-Object { "$($_.Hash.ToLower())  MAVIS-Windows-Setup.exe" } | Set-Content dist/MAVIS-Windows-SHA256SUMS.txt
