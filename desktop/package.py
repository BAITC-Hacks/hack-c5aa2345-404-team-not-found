"""Package the complete portable directory and dependency license notices."""
from hashlib import sha256
from importlib import metadata
from pathlib import Path
import shutil
import zipfile

root = Path(__file__).resolve().parent
bundle = root / "out" / "SAMRUK-KAZYNA"
if not (bundle / "SAMRUK-KAZYNA.exe").is_file():
    raise SystemExit("Build the EXE before packaging")
shutil.copy2(root / "PORTABLE-README.txt", bundle / "README.txt")
notices = bundle / "THIRD-PARTY-LICENSES"
notices.mkdir(exist_ok=True)
summary = []
for dist in sorted(metadata.distributions(), key=lambda item: item.metadata["Name"].lower()):
    name = dist.metadata["Name"]
    summary.append(f"{name}=={dist.version}\n{dist.metadata.get('License-Expression') or dist.metadata.get('License', 'See package license')}\n")
    for entry in dist.files or []:
        filename = entry.name.lower()
        if filename.startswith(("license", "copying", "notice")):
            source = Path(dist.locate_file(entry))
            if source.is_file():
                target = notices / name / str(entry)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
(notices / "DEPENDENCIES.txt").write_text("\n".join(summary), encoding="utf-8")
release = root / "release"
release.mkdir(exist_ok=True)
archive = release / "SAMRUK-KAZYNA-windows-x64.zip"
with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=5) as output:
    for path in sorted(bundle.rglob("*")):
        if path.is_file():
            output.write(path, path.relative_to(bundle.parent))
digest = sha256()
with archive.open("rb") as stream:
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
(release / "SHA256SUMS.txt").write_text(f"{digest.hexdigest()}  {archive.name}\n", encoding="ascii")
print(f"{archive}\nSHA256: {digest.hexdigest()}")
