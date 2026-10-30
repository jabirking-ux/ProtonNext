import os
import sys
import shutil
import zipfile
import subprocess
from pathlib import Path

def main():
    root = Path(__file__).resolve().parent.parent
    bin_dir = root / "win-app" / "src" / "bin"
    cli_dir = root / "ProtonVPN-Next-CLI"
    installer_proj_dir = root / "installer" / "src" / "ProtonNextInstaller"
    payload_zip = installer_proj_dir / "payload.zip"
    publish_dir = root / "installer" / "publish"
    output_exe = root / "ProtonNext-Setup.exe"

    print("=== ProtonNext Handmade Fast Installer Builder ===")
    print(f"Root: {root}")

    if not bin_dir.exists():
        print(f"Error: {bin_dir} does not exist. Please build win-app first.")
        sys.exit(1)

    print(f"[1/3] Creating payload archive: {payload_zip} ...")
    if payload_zip.exists():
        payload_zip.unlink()

    ignore_patterns = {".git", "__pycache__", "result", ".vs", "obj"}
    ignore_extensions = {".pyc", ".tmp", ".pdb"}

    with zipfile.ZipFile(payload_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=4) as zf:
        # Add win-app/src/bin files to root of archive
        print("  - Adding win-app/src/bin files...")
        count = 0
        for p in bin_dir.rglob("*"):
            if p.is_file():
                if any(part in ignore_patterns for part in p.parts):
                    continue
                if p.suffix.lower() in ignore_extensions:
                    continue
                rel_path = p.relative_to(bin_dir)
                zf.write(p, str(rel_path).replace("\\", "/"))
                count += 1
        print(f"    Added {count} files from win-app/src/bin")

        # Add ProtonVPN-Next-CLI files
        print("  - Adding ProtonVPN-Next-CLI files...")
        cli_count = 0
        for p in cli_dir.rglob("*"):
            if p.is_file():
                if any(part in ignore_patterns for part in p.parts):
                    continue
                if p.suffix.lower() in ignore_extensions:
                    continue
                rel_path = Path("ProtonVPN-Next-CLI") / p.relative_to(cli_dir)
                zf.write(p, str(rel_path).replace("\\", "/"))
                cli_count += 1
        print(f"    Added {cli_count} files from ProtonVPN-Next-CLI")

    zip_size_mb = payload_zip.stat().st_size / (1024 * 1024)
    print(f"Payload archive size: {zip_size_mb:.2f} MB")

    print("[2/3] Compiling standalone single-file installer binary with .NET...")
    proj_file = installer_proj_dir / "ProtonNextInstaller.csproj"
    cmd = [
        "dotnet", "publish", str(proj_file),
        "-c", "Release",
        "-r", "win-x64",
        "--self-contained", "true",
        "-p:PublishSingleFile=true",
        "-p:EnableCompressionInSingleFile=true",
        "-p:IncludeNativeLibrariesForSelfExtract=true",
        "-o", str(publish_dir)
    ]
    print(f"Running: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=str(root))
    if res.returncode != 0:
        print(f"Error: dotnet publish failed with code {res.returncode}")
        sys.exit(res.returncode)

    built_exe = publish_dir / "ProtonNext-Setup.exe"
    if not built_exe.exists():
        print(f"Error: {built_exe} not found after publish.")
        sys.exit(1)

    print(f"[3/3] Copying output installer to {output_exe} ...")
    if output_exe.exists():
        output_exe.unlink()
    shutil.copy2(built_exe, output_exe)

    # Cleanup temporary payload zip and publish folder to keep workspace tidy
    try:
        payload_zip.unlink(missing_ok=True)
        shutil.rmtree(publish_dir, ignore_errors=True)
    except Exception as e:
        print(f"Notice: cleanup warning: {e}")

    out_size_mb = output_exe.stat().st_size / (1024 * 1024)
    print("==================================================")
    print(f"SUCCESS: Created {output_exe} ({out_size_mb:.2f} MB)")
    print("==================================================")

if __name__ == "__main__":
    main()
