# -*- mode: python -*-

block_cipher = None


a = Analysis(['buildbot-worker.py'],
             pathex=[],
             binaries=[],
             datas=[],
             hiddenimports=["buildbot_worker", "buildbot_worker.scripts.create_worker", "buildbot_worker.scripts.start", "buildbot_worker.scripts.stop", "buildbot_worker.scripts.restart", "buildbot_worker.bot"],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='buildbot-worker',
          debug=False,
          strip=False,
          upx=True,
          runtime_tmpdir=None,
          console=True )
