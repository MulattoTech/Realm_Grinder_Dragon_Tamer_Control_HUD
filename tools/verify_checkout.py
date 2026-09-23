"""Verify committed source in a temporary checkout without private runtime files."""
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile
ROOT=Path(__file__).resolve().parents[1]

def main():
    source=subprocess.run(['git','archive','--format=zip','HEAD'],cwd=ROOT,check=True,stdout=subprocess.PIPE).stdout
    with tempfile.TemporaryDirectory(prefix='realm-grinder-clean-') as folder:
        target=Path(folder)
        with zipfile.ZipFile(io.BytesIO(source)) as archive:
            for member in archive.infolist():
                resolved=(target/member.filename).resolve()
                if not resolved.is_relative_to(target.resolve()):raise ValueError('Invalid archive path')
            archive.extractall(target)
        checks=[]
        for args in ([sys.executable,'tools/bootstrap.py','--game-dir',str(target/'missing-game')],
                     [sys.executable,'-m','compileall','-q','src','tools','launcher.py'],
                     [sys.executable,'-m','pytest','-q','--tb=short','-p','no:cacheprovider']):
            result=subprocess.run(args,cwd=target,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,
                                  encoding='utf-8',errors='replace',timeout=90)
            print(result.stdout,flush=True)
            checks.append({'command':args[1:],'returncode':result.returncode,'output':result.stdout})
            if result.returncode:break
        report={'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                'private_runtime_copied':False,'checks':checks,'passed':all(item['returncode']==0 for item in checks)}
        (ROOT/'logs').mkdir(exist_ok=True)
        (ROOT/'logs/clean-checkout-verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        return 0 if report['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
