#!/usr/bin/env python3
"""Extract embedded (obfuscated) fonts from the course templates and install them
into the user font directory so LibreOffice can render the templates correctly.

Office stores embedded fonts as .odttf: the raw TTF with its first 32 bytes
XOR-ed against the font's GUID (16 bytes, applied twice). Reversing that gives
back a normal TTF that fontconfig can use.

Reads the templates only - never modifies them.
"""
import glob
import os
import re
import subprocess
import sys
import zipfile
import xml.etree.ElementTree as ET

TEMPLATES = "/home/hadoop/capstone/templates"
DEST = os.path.expanduser("~/.local/share/fonts/course-templates")

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"

EMBED_TAGS = {
    "embedRegular": "regular",
    "embedBold": "bold",
    "embedItalic": "italic",
    "embedBoldItalic": "bolditalic",
}


def deobfuscate(data: bytes, guid: str) -> bytes:
    # The GUID's 16 bytes are consumed in reverse order; verified empirically
    # against all four embedded fonts in the Action Plan (each then starts with
    # the TrueType signature 0x00010000).
    raw = bytes.fromhex(guid.strip("{}").replace("-", ""))[::-1]
    payload = bytearray(data)
    for i in range(min(32, len(payload))):
        payload[i] ^= raw[i % 16]
    return bytes(payload)


def find_font_table(names):
    for cand in ("word/fontTable.xml", "ppt/fonts/fontTable.xml"):
        if cand in names:
            return cand
    return None


def extract_from(path, outdir):
    installed = []
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        table = find_font_table(names)
        if table is None:
            return installed

        base = table.rsplit("/", 1)[0] if "/" in table else ""
        relpath = f"{base}/_rels/{os.path.basename(table)}.rels" if base else ""
        relmap = {}
        if relpath in names:
            root = ET.fromstring(z.read(relpath))
            for rel in root:
                relmap[rel.get("Id")] = rel.get("Target")

        root = ET.fromstring(z.read(table))
        for font in root.iter(f"{W}font"):
            name = font.get(f"{W}name")
            for tag, style in EMBED_TAGS.items():
                node = font.find(f"{W}{tag}")
                if node is None:
                    continue
                rid = node.get(f"{R}id")
                guid = node.get(f"{W}fontKey")
                if not rid or not guid:
                    continue
                target = relmap.get(rid)
                if not target:
                    continue
                member = os.path.normpath(
                    os.path.join(base, target) if base else target
                ).replace("\\", "/")
                if member not in names:
                    continue
                data = deobfuscate(z.read(member), guid)
                safe = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-")
                out = os.path.join(outdir, f"{safe}-{style}.ttf")
                if not os.path.exists(out):
                    with open(out, "wb") as fh:
                        fh.write(data)
                    installed.append((name, style, out))
    return installed


def main():
    os.makedirs(DEST, exist_ok=True)
    total = []
    for path in sorted(glob.glob(os.path.join(TEMPLATES, "*"))):
        base = os.path.basename(path)
        if base.startswith("~$") or not base.endswith((".docx", ".pptx")):
            continue
        try:
            got = extract_from(path, DEST)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! {base}: {type(exc).__name__}: {exc}")
            continue
        if got:
            print(f"{base}:")
            for name, style, out in got:
                print(f"   {name} [{style}] -> {os.path.basename(out)}")
        total += got

    if not total:
        print("no embedded fonts found")
        return 1

    bad = []
    for _, _, out in total:
        with open(out, "rb") as fh:
            sig = fh.read(4)
        if sig not in (b"\x00\x01\x00\x00", b"OTTO", b"true", b"ttcf"):
            bad.append((os.path.basename(out), sig))
    if bad:
        print("\n!! unexpected signature (de-obfuscation may have failed):")
        for name, sig in bad:
            print(f"   {name}: {sig!r}")
    else:
        print(f"\nall {len(total)} extracted files have a valid font signature")

    subprocess.run(["fc-cache", "-f", DEST], capture_output=True)
    print("fc-cache done")
    for probe in ("SamsungOne 400", "SamsungOne 700", "Samsung Sharp Sans"):
        r = subprocess.run(["fc-match", probe], capture_output=True, text=True)
        print(f"  fc-match {probe!r} -> {r.stdout.strip()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
