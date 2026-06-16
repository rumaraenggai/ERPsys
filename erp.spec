# erp.spec  —  PyInstaller packaging spec
# Run:  pyinstaller erp.spec

import os
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

added_files = [
    ("templates", "templates"),
    ("static",    "static"),
]

a = Analysis(
    ["app.py"],
    pathex=[os.path.abspath(".")],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        "flask",
        "jinja2",
        "werkzeug",
        "click",
        "zk",           # pyzk
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas,
    name="MiniERP",
    debug=False,
    strip=False,
    upx=True,
    console=False,          # No terminal window — looks like a real desktop app
    icon=None,              # Add your .ico path here if you have one
)
