"""构建、离线安装验证并校验协议分发物；与 Git 托管平台无关。"""
import argparse
import hashlib
import os
import subprocess
import sys
import tempfile
from zipfile import ZipFile
from email.parser import Parser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from resume_contracts import VERSION


def verify_wheel(wheel):
    with tempfile.TemporaryDirectory(prefix="resume-contract-wheel-") as temporary:
        venv = Path(temporary) / "venv"
        subprocess.run([sys.executable, "-m", "venv", "--system-site-packages", str(venv)], check=True)
        python = venv / "bin/python"
        environment = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
        # CI 已安装同版本 SDK；继承的包只能供应依赖，不能代替待验证 wheel。
        # ignore-installed 不卸载父环境的包，并确保在子环境生成 console script。
        subprocess.run([
            str(python), "-m", "pip", "install", "--ignore-installed",
            "--no-deps", "--no-index", str(wheel),
        ], cwd=temporary, env=environment, check=True)
        subprocess.run([
            str(python), "-c",
            "from pathlib import Path; import sys, resume_contracts; "
            "source = Path(resume_contracts.__file__).resolve(); "
            "prefix = Path(sys.prefix).resolve(); "
            "source.relative_to(prefix)",
        ], cwd=temporary, env=environment, check=True)
        subprocess.run([str(python), "-m", "resume_contracts.verify"], cwd=temporary, env=environment, check=True)
        subprocess.run([str(venv / "bin/resume-kernel-mock"), "--help"], cwd=temporary, env=environment, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="")
    args = parser.parse_args()
    if args.version and args.version != "v" + VERSION:
        raise SystemExit("发布标签必须与协议包版本一致")
    output = ROOT / "dist" / ("v" + VERSION)
    if output.exists():
        raise SystemExit("分发目录已存在，请使用新版本或单独保存旧产物后重试")
    # 调用者提前安装 build/setuptools/wheel；构建过程不隐式下载构建依赖。
    subprocess.run([sys.executable, "-m", "build", "--no-isolation", "--outdir", str(output)], cwd=ROOT, check=True)
    wheels = list(output.glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit("必须且仅有一个 wheel")
    with ZipFile(wheels[0]) as archive:
        metadata_path = next(name for name in archive.namelist() if name.endswith(".dist-info/METADATA"))
        metadata = Parser().parsestr(archive.read(metadata_path).decode())
        if metadata["Version"] != VERSION:
            raise SystemExit("pyproject 包版本与 SDK VERSION 不一致")
    verify_wheel(wheels[0])
    files = sorted(p for p in output.iterdir() if p.suffix == ".whl" or p.name.endswith(".tar.gz"))
    (output / "SHA256SUMS").write_text("".join(hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n" for p in files))
    print(output)

if __name__ == "__main__":
    main()
