# targem installer for Windows: Python, Tesseract OCR, targem, the offline Hebrew model, and shortcuts.
# Double-click install.bat, or paste into PowerShell:
#   irm https://raw.githubusercontent.com/GbaGuy/targem/main/install.ps1 | iex
# Remove everything again:  install.bat -Uninstall
param([switch]$Uninstall)
$ErrorActionPreference = "Stop"

$dir = "$env:LOCALAPPDATA\targem"
$links = @("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\targem.lnk",
           "$([Environment]::GetFolderPath('Desktop'))\targem.lnk")

if ($Uninstall) {
    Get-Process pythonw -ErrorAction SilentlyContinue | Where-Object { $_.Path -like "$dir*" } | Stop-Process
    Remove-Item -Recurse -Force (@($dir, "$env:USERPROFILE\.local\share\targem") + $links) -ErrorAction SilentlyContinue
    Write-Host "targem removed. (Python and Tesseract were left installed.)"
    return
}

function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
}

function Works($block) {
    try { & $block *> $null; return $LASTEXITCODE -eq 0 } catch { return $false }
}

function Need($name, $wingetId, $test) {
    if (Works $test) { return }
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "$name is missing and winget isn't available. Install $name yourself, then run this again."
    }
    Write-Host "Installing $name ..."
    winget install --id $wingetId -e --silent --accept-package-agreements --accept-source-agreements
    Refresh-Path
    if (-not (Works $test)) { throw "$name didn't install. Install it yourself, then run this again." }
}

Need "Python 3.12" "Python.Python.3.12" { py -3.12 -c "pass" }
Need "Tesseract OCR" "UB-Mannheim.TesseractOCR" {
    if (-not (Test-Path "$env:ProgramFiles\Tesseract-OCR\tesseract.exe")) { tesseract --version }
}

Write-Host "Installing targem to $dir ..."
New-Item -ItemType Directory -Force $dir | Out-Null
if ($PSScriptRoot -and (Test-Path "$PSScriptRoot\targem.py")) {
    Copy-Item "$PSScriptRoot\*" $dir -Recurse -Force -Exclude ".git", ".venv"   # running from a download/clone
} else {
    $zip = "$env:TEMP\targem.zip"
    Invoke-WebRequest "https://github.com/GbaGuy/targem/archive/refs/heads/main.zip" -OutFile $zip
    Expand-Archive $zip "$env:TEMP\targem-src" -Force
    Copy-Item "$env:TEMP\targem-src\targem-main\*" $dir -Recurse -Force
    Remove-Item -Recurse -Force $zip, "$env:TEMP\targem-src"
}

$py = "$dir\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { py -3.12 -m venv "$dir\.venv" }
& $py -m pip install --quiet --disable-pip-version-check pillow ctranslate2 sentencepiece
if ($LASTEXITCODE) { throw "pip install failed" }

Write-Host "Downloading the offline Hebrew model (120 MB) ..."
& $py "$dir\targem.py" --setup-offline
if ($LASTEXITCODE) { throw "model download failed" }

$shell = New-Object -ComObject WScript.Shell
foreach ($path in $links) {
    $lnk = $shell.CreateShortcut($path)
    $lnk.TargetPath = "$dir\.venv\Scripts\pythonw.exe"
    $lnk.Arguments = "`"$dir\targem.py`" --offline"
    $lnk.WorkingDirectory = $dir
    $lnk.IconLocation = "$dir\icon.ico"
    $lnk.Description = "targem - on-screen Hebrew translator for games"
    $lnk.Save()
}

Write-Host ""
Write-Host "Done! targem is in the Start Menu and on your desktop. Starting it now..."
Write-Host "Hotkeys: Ctrl+Alt+T translate, Ctrl+Alt+R again, Ctrl+Alt+L live, Ctrl+Alt+X close."
Start-Process "$dir\.venv\Scripts\pythonw.exe" -ArgumentList "`"$dir\targem.py`" --offline" -WorkingDirectory $dir
