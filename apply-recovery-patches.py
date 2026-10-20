#!/usr/bin/env python3
"""Apply authored native-recovery patches after repo sync; never fetch or reset."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent


def git(project, *args, env=None):
    return subprocess.run(["git", *args], cwd=project, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, help="Android repo checkout")
    parser.add_argument("--check", action="store_true", help="preflight only")
    args = parser.parse_args()
    root = args.root or next((p for p in HERE.parents if (p / ".repo").is_dir()), None)
    if root is None:
        parser.error("pass --root pointing to an Android repo checkout")
    root = root.resolve()
    series = json.loads((HERE / "patches/series.json").read_text())
    if series.get("version") != 1:
        raise RuntimeError("unsupported patch series version")
    pending = []
    for entry in series["projects"]:
        project = (root / entry["path"]).resolve()
        project.relative_to(root)
        status = git(project, "status", "--porcelain")
        if status.returncode or status.stdout:
            raise RuntimeError(f"{entry['path']}: missing Git checkout or uncommitted changes")
        for marker in ("rebase-apply", "rebase-merge", "CHERRY_PICK_HEAD", "MERGE_HEAD"):
            result = git(project, "rev-parse", "--git-path", marker)
            if result.returncode:
                raise RuntimeError(result.stderr.strip())
            if (project / result.stdout.strip()).exists():
                raise RuntimeError(f"{entry['path']}: unfinished Git operation")
        with tempfile.TemporaryDirectory(prefix="recovery-patch-index-") as temp:
            env = dict(os.environ, GIT_INDEX_FILE=str(Path(temp) / "index"))
            result = git(project, "read-tree", "HEAD", env=env)
            if result.returncode:
                raise RuntimeError(result.stderr.strip())
            # Check the complete applied stack backwards: later patches may
            # modify an earlier patch's context, so individual reverse checks
            # alone cannot recognize a fully applied dependent series.
            validated = []
            for item in entry["patches"]:
                patch = (HERE / item["file"]).resolve()
                patch.relative_to(HERE)
                if hashlib.sha256(patch.read_bytes()).hexdigest() != item["sha256"]:
                    raise RuntimeError(f"patch checksum mismatch: {item['file']}")
                validated.append(patch)
            already_applied = True
            for patch in reversed(validated):
                if git(project, "apply", "--cached", "--reverse", str(patch), env=env).returncode:
                    already_applied = False
                    break
            result = git(project, "read-tree", "HEAD", env=env)
            if result.returncode:
                raise RuntimeError(result.stderr.strip())
            if already_applied:
                pending.append((entry["path"], project, []))
                continue
            patches = []
            for item in entry["patches"]:
                patch = (HERE / item["file"]).resolve()
                patch.relative_to(HERE)
                if hashlib.sha256(patch.read_bytes()).hexdigest() != item["sha256"]:
                    raise RuntimeError(f"patch checksum mismatch: {item['file']}")
                result = git(project, "apply", "--cached", str(patch), env=env)
                if result.returncode:
                    reverse = git(project, "apply", "--cached", "--reverse", "--check", str(patch), env=env)
                    if reverse.returncode:
                        raise RuntimeError(f"{entry['path']}: patch needs review; no changes made:\n{result.stderr}")
                else:
                    patches.append(patch)
            pending.append((entry["path"], project, patches))
    # Every project passes before any real index or worktree is modified.
    for name, project, patches in pending:
        if args.check:
            print(f"{name}: {len(patches)} patches pending (preflight passed)")
        elif patches:
            result = git(project, "am", *map(str, patches))
            if result.returncode:
                git(project, "am", "--abort")
                raise RuntimeError(f"{name}: git am failed and was aborted:\n{result.stderr}")
            print(f"{name}: applied {len(patches)} authored patches")
        else:
            print(f"{name}: already applied")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError, ValueError) as error:
        raise SystemExit(str(error))
