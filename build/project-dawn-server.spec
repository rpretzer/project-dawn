# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['/home/rpretzer/project-dawn/server_p2p.py'],
    pathex=[],
    binaries=[],
    datas=[('/home/rpretzer/project-dawn/frontend', 'frontend'), ('/home/rpretzer/project-dawn/agents', 'agents'), ('/home/rpretzer/project-dawn/mcp', 'mcp'), ('/home/rpretzer/project-dawn/p2p', 'p2p'), ('/home/rpretzer/project-dawn/crypto', 'crypto'), ('/home/rpretzer/project-dawn/consensus', 'consensus'), ('/home/rpretzer/project-dawn/host', 'host')],
    hiddenimports=['asyncio', 'websockets', 'aiohttp'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='project-dawn-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
