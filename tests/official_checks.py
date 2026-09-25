#!/usr/bin/env python3
"""Run the same checks the official Cinnamon Spices CI runs on a pull request.

Both tools are downloaded fresh on every run, so the checks always match the
current official rules:
  - validate-spice   (linuxmint/cinnamon-spices-desklets): folder layout,
                     info.json, metadata.json, square icon, translations
  - Pattern Check    (linuxmint/github-actions): deprecated / forbidden APIs
                     and code conventions, as regex rules

Requires: python3-pil, python3-yaml, network access.
Usage:    tests/official_checks.py
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request

import yaml

UUID = "workspace-switcher-desklet@mgldvd"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

VALIDATE_URL = "https://raw.githubusercontent.com/linuxmint/cinnamon-spices-desklets/master/validate-spice"
PATTERNS_TREE = "https://api.github.com/repos/linuxmint/github-actions/git/trees/master?recursive=1"
PATTERNS_RAW = "https://raw.githubusercontent.com/linuxmint/github-actions/master/"


def fetch(url):
    with urllib.request.urlopen(url, timeout=30) as response:
        return response.read().decode()


def run_validate_spice():
    print("== validate-spice (official) ==", flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        script = os.path.join(tmp, "validate-spice")
        with open(script, "w") as f:
            f.write(fetch(VALIDATE_URL))
        result = subprocess.run([sys.executable, script, UUID], cwd=ROOT)
    return result.returncode == 0


def run_pattern_check():
    print("\n== Pattern Check (official rules) ==")
    tree = json.loads(fetch(PATTERNS_TREE))["tree"]
    rule_files = [item["path"] for item in tree
                  if item["path"].startswith("pattern-checker/patterns/") and item["path"].endswith(".yml")]

    rules = []
    for path in rule_files:
        rules += (yaml.safe_load(fetch(PATTERNS_RAW + path)) or {}).get("patterns", [])

    files = []
    for dirpath, _, names in os.walk(os.path.join(ROOT, UUID)):
        files += [os.path.join(dirpath, name) for name in names]

    errors = warnings = 0
    for rule in rules:
        extensions = rule.get("extensions") or []
        for path in files:
            if extensions and not any(path.endswith(ext) for ext in extensions):
                continue
            try:
                lines = open(path, encoding="utf-8").read().splitlines()
            except UnicodeDecodeError:
                continue
            for number, line in enumerate(lines, 1):
                if re.search(rule["regex"], line):
                    severity = rule.get("severity", "warning")
                    errors += severity == "error"
                    warnings += severity != "error"
                    print(f"[{severity}] {rule['name']}: {os.path.relpath(path, ROOT)}:{number}")
                    print("    " + rule.get("message", "").strip().splitlines()[0])

    print(f"{len(rules)} rules from {len(rule_files)} files: {errors} errors, {warnings} warnings")
    return errors == 0 and warnings == 0


if __name__ == "__main__":
    ok = run_validate_spice()
    ok = run_pattern_check() and ok
    print("\nALL OFFICIAL CHECKS PASSED" if ok else "\nOFFICIAL CHECKS FAILED")
    sys.exit(0 if ok else 1)
