# -*- mode: python ; coding: utf-8 -*-
"""
Scene Dialogue Demo - PyInstaller spec
"""

import os
import sys
from pathlib import Path

project_root = os.path.dirname(os.path.dirname(os.path.abspath(SPEC)))

required_datas = [
    (os.path.join(project_root, 'static'), 'static'),
    (os.path.join(project_root, 'template_bank', 'industry_skeleton'), 'template_bank/industry_skeleton'),
    (os.path.join(project_root, 'domain_kb'), 'domain_kb'),
    (os.path.join(project_root, 'demo'), 'demo'),
    (os.path.join(project_root, 'requirements.txt'), '.'),
]

optional_datas = [
    # (os.path.join(project_root, 'tools'), 'tools'),
    # (os.path.join(project_root, 'output'), 'output'),
    # (os.path.join(project_root, 'audio'), 'audio'),
    # (os.path.join(project_root, 'output_ja'), 'output_ja'),
    # (os.path.join(project_root, 'audio_ja'), 'audio_ja'),
]

datas = required_datas + optional_datas
binaries = []

if sys.platform == 'win32':
    import sysconfig

    python_dir = Path(sysconfig.get_config_var('prefix'))
    python_dll = None

    for dll_name in [
        f'python{sys.version_info.major}{sys.version_info.minor}.dll',
        f'python3{sys.version_info.minor}.dll',
        'python3.dll',
    ]:
        dll_path = python_dir / dll_name
        if dll_path.exists():
            python_dll = str(dll_path)
            binaries.append((python_dll, '.'))
            print(f"[build] include Python DLL: {python_dll}")
            break

    if not python_dll:
        dlls_dir = python_dir / 'DLLs'
        if dlls_dir.exists():
            for dll_file in dlls_dir.glob('python*.dll'):
                binaries.append((str(dll_file), '.'))
                print(f"[build] include Python DLL: {dll_file}")
                break

ffmpeg_win = os.path.join(project_root, 'bin', 'ffmpeg.exe')
if sys.platform == 'win32' and os.path.exists(ffmpeg_win):
    binaries.append((ffmpeg_win, 'bin'))
    print(f"[build] include ffmpeg.exe: {ffmpeg_win}")

ffmpeg_unix = os.path.join(project_root, 'bin', 'ffmpeg')
if sys.platform in ['darwin', 'linux'] and os.path.exists(ffmpeg_unix):
    binaries.append((ffmpeg_unix, 'bin'))
    print(f"[build] include ffmpeg: {ffmpeg_unix}")

hiddenimports = [
    'tornado.web',
    'tornado.ioloop',
    'tornado.websocket',
    'numpy',
    'deep_translator',
    'edge_tts',
    'pydub',
    'webview',
]

block_cipher = None

a = Analysis(
    [os.path.join(project_root, 'app.py')],
    pathex=[project_root],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='SceneDialogueDemo',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
    manifest=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SceneDialogueDemo',
)

if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='SceneDialogueDemo.app',
        icon=None,
        bundle_identifier='com.scenedialogue.demo',
        info_plist={
            'CFBundleName': 'Scene Dialogue Demo',
            'CFBundleDisplayName': 'Scene Dialogue Demo',
            'CFBundleVersion': '2.0.0',
            'CFBundleShortVersionString': '2.0.0',
            'NSHighResolutionCapable': 'True',
        },
    )
