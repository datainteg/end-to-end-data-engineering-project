"""Create portable dependency-free project/Lambda zips; SDKs supplied separately."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
ROOT = Path(__file__).resolve().parents[1]
out = ROOT / ".runtime/packages"
out.mkdir(parents=True, exist_ok=True)
with ZipFile(out/"pipeline.zip", "w", ZIP_DEFLATED) as z:
    for folder in ["pipeline", "scripts"]:
        for p in (ROOT/folder).glob("*.py"):
            z.write(p,p.relative_to(ROOT))
for name in ["validate_manifest","pipeline_lock"]:
    with ZipFile(out/f"{name}.zip", "w", ZIP_DEFLATED) as z:
        z.write(ROOT/f"lambdas/{name}/handler.py","handler.py")
        for p in (ROOT/"pipeline").glob("*.py"):
            z.write(p,p.relative_to(ROOT))
print(out)
