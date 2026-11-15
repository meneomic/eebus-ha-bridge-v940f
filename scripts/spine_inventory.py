#!/usr/bin/env python3
"""Summarise the existing [DISCOVERY] diagnostic log without contacting EEBUS.

Output intentionally excludes SKIs and unrecognised log text. Advertised SPINE
permissions are capabilities, *not* proof that a function returns a value or
that a command can be safely executed.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEVICE = re.compile(r"^device\s+ski=\S+\s+type=(\S+)\s+entities=(\d+)\s*$")
ENTITY = re.compile(r"^entity\s+addr=(\S+)\s+type=(\S+)\s+features=\[(.*)]\s*$")
FEATURE = re.compile(
    r"^feature\s+addr=(\S+)\s+type=(\S+)\s+role=(\S+)\s+functions=\[(.*)]\s*$"
)
USECASE = re.compile(
    r"^usecase\s+actor=(\S+)\s+name=(\S+)\s+v(\S*)\s+available=(true|false)\s+scenarios=\[([\d,]*)]\s*$"
)
FUNCTION = re.compile(r"([A-Za-z0-9_]+)\(([a-z,\s-]*)\)")
OPERATIONS = {"r", "rp", "w", "wp"}


def parse(text: str) -> list[dict]:
    """Parse one or multiple diagnostic device dumps; discard SKI and raw log."""
    devices: list[dict] = []
    current: dict | None = None
    for line in text.splitlines():
        # Go's log.Printf can prefix the first line of a multiline discovery.
        if "[DISCOVERY]" not in line:
            continue
        content = line.split("[DISCOVERY]", 1)[1].strip()
        if match := DEVICE.fullmatch(content):
            current = {
                "index": len(devices) + 1,
                "device_type": match.group(1),
                "declared_entities": int(match.group(2)),
                "entities": [],
                "features": [],
                "use_cases": [],
            }
            devices.append(current)
            continue
        if current is None:
            continue
        if match := ENTITY.fullmatch(content):
            current["entities"].append({
                "address": match.group(1),
                "type": match.group(2),
            })
        elif match := FEATURE.fullmatch(content):
            addr, kind, role, body = match.groups()
            functions = []
            for fn in FUNCTION.finditer(body):
                permissions = [p.strip() for p in fn.group(2).split(",") if p.strip() in OPERATIONS]
                functions.append({"name": fn.group(1), "operations": permissions})
            current["features"].append({
                "address": addr, "type": kind, "role": role, "functions": functions,
            })
        elif match := USECASE.fullmatch(content):
            actor, name, version, available, scenarios = match.groups()
            current["use_cases"].append({
                "actor": actor, "name": name, "version": version,
                "available": available == "true",
                "scenarios": [int(n) for n in scenarios.split(",") if n],
            })
    return devices


def markdown(devices: list[dict]) -> str:
    lines = [
        "# Inventaire EEBUS/SPINE (lecture seule)", "",
        "Source : lignes [DISCOVERY] du bridge Go. Les SKI et les autres",
        "lignes de journal ne sont pas reproduits.", "",
        "**Important :** r/rp/w/wp sont des permissions *annoncées* :",
        "elles ne prouvent ni la présence d'une mesure actuelle, ni le succès",
        "ou la sécurité d'une commande. Aucune requête n'est envoyée à Vaillant.", "",
    ]
    for item in devices:
        lines += [
            f"## Appareil {item['index']} — {item['device_type']}", "",
            f"Entités annoncées : {item['declared_entities']} ; entités observées : {len(item['entities'])} ; fonctions observées : {sum(len(f['functions']) for f in item['features'])}.", "",
            "### Fonctions et droits annoncés", "",
            "| Adresse | Fonctionnalité | Rôle | Fonction | Droits |", "|---|---|---|---|---|",
        ]
        for feature in item["features"]:
            if not feature["functions"]:
                lines.append(f"| {feature['address']} | {feature['type']} | {feature['role']} | — | — |")
            for function in feature["functions"]:
                ops = ", ".join(function["operations"]) or "aucun"
                lines.append(f"| {feature['address']} | {feature['type']} | {feature['role']} | {function['name']} | {ops} |")
        lines += ["", "### Use cases annoncés", "", "| Acteur | Nom | Version | Disponible | Scénarios |", "|---|---|---|---|---|"]
        for uc in item["use_cases"]:
            scenarios = ", ".join(str(v) for v in uc["scenarios"]) or "—"
            lines.append(f"| {uc['actor']} | {uc['name']} | {uc['version']} | {'oui' if uc['available'] else 'non'} | {scenarios} |")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logfile", type=Path, help="Journal texte exporté du bridge (fichier local)")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", type=Path, help="Chemin de sortie ; sinon stdout")
    args = parser.parse_args()
    try:
        data = args.logfile.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        parser.error(str(exc))
    devices = parse(data)
    if not devices or not any(d["features"] for d in devices):
        print("Aucun inventaire SPINE exploitable. Activer debug_events sur un bridge compatible, puis relancer une découverte complète.", file=sys.stderr)
        return 2
    output = json.dumps({"devices": devices}, ensure_ascii=False, indent=2) if args.format == "json" else markdown(devices)
    if args.output:
        try:
            args.output.write_text(output + "\n", encoding="utf-8")
        except OSError as exc:
            parser.error(str(exc))
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
