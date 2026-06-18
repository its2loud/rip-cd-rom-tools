#!/usr/bin/env python3
"""carve_audio.py — Audiobereich aus einer Mixed-Mode-BIN (OHNE --read-raw) extrahieren.

Wenn der Datentrack 2048 B/Sektor hat (cdrdao ohne --read-raw), kann bchunk die gemischte
BIN nicht direkt zerlegen. Dieses Script löst das autark in einem Schritt:
  1. schneidet den reinen Audiobereich heraus  -> audio-only.bin (durchgängig 2352 B)
  2. schreibt die passende all-Audio-CUE       -> audio-only.cue
Danach normal: bchunk -w audio-only.bin audio-only.cue track

Offset und Trackgrenzen liest es selbst aus der cdrdao-.toc:
  Offset            = Datentrack-Länge (DATAFILE-MSF) × Sektorgröße (MODE1=2048, MODE1_RAW=2352)
  INDEX 01 je Track = laufende Summe der bisherigen Audiotrack-Längen (Datei ist lückenlos)

WICHTIG: game.bin muss bereits little-endian sein (swab_audio.py), sonst rauschen die WAVs.

Aufruf: carve_audio.py <game.bin> <game.toc> [-o outdir]
"""
import argparse, os, re, sys

DATA_SECTOR = {"MODE1": 2048, "MODE1_RAW": 2352, "MODE2": 2336,
               "MODE2_RAW": 2352, "MODE2_FORM1": 2336}
CHUNK = 16 * 1024 * 1024

def msf_to_frames(m, s, f):
    return (m * 60 + s) * 75 + f

def frames_to_msf(fr):
    m = fr // 4500; fr -= m * 4500          # 4500 Frames = 1 Minute (75 * 60)
    return f"{m:02d}:{fr // 75:02d}:{fr % 75:02d}"

def parse_toc(tocpath):
    text = open(tocpath, encoding="utf-8", errors="replace").read()
    # Sektorgröße aus dem ersten Nicht-Audio-TRACK
    mode = next((m.group(1).upper() for ln in text.splitlines()
                 if (m := re.match(r'TRACK\s+(\S+)', ln.strip())) and m.group(1).upper() != "AUDIO"),
                None)
    if mode not in DATA_SECTOR:
        sys.exit(f"FEHLER: Datentrack-Modus '{mode}' nicht unterstützt ({', '.join(DATA_SECTOR)}).")
    dm = re.search(r'DATAFILE\s+"[^"]*"\s+(?:#\d+\s+)?(\d+):(\d+):(\d+)', text)
    if not dm:
        sys.exit("FEHLER: DATAFILE-Länge in der TOC nicht gefunden.")
    data_frames = msf_to_frames(int(dm[1]), int(dm[2]), int(dm[3]))
    # Audiotrack-Längen: letzte MSF der ersten FILE-Zeile je TRACK-AUDIO-Block
    lengths, in_audio = [], False
    for ln in text.splitlines():
        st = ln.strip()
        if st.startswith("TRACK AUDIO"):
            in_audio = True
        elif st.startswith("TRACK "):
            in_audio = False
        elif in_audio and st.startswith("FILE"):
            msfs = re.findall(r'(\d+):(\d+):(\d+)', st)
            if msfs:
                lengths.append(msf_to_frames(*map(int, msfs[-1])))
                in_audio = False
    return DATA_SECTOR[mode], data_frames, lengths

def main():
    ap = argparse.ArgumentParser(description="Audiobereich + all-Audio-CUE aus Mixed-Mode-BIN")
    ap.add_argument("bin")
    ap.add_argument("toc")
    ap.add_argument("-o", "--outdir", help="Zielordner (Default: neben der BIN)")
    args = ap.parse_args()

    dsize, data_frames, lengths = parse_toc(args.toc)
    offset = data_frames * dsize
    size = os.path.getsize(args.bin)
    if not (0 < offset < size):
        sys.exit(f"FEHLER: Offset {offset} liegt nicht in der Datei ({size} B) — TOC/BIN passen nicht?")

    outdir = args.outdir or os.path.dirname(os.path.abspath(args.bin))
    os.makedirs(outdir, exist_ok=True)
    binout = os.path.join(outdir, "audio-only.bin")
    cueout = os.path.join(outdir, "audio-only.cue")

    print(f"Datentrack: {data_frames} Frames x {dsize} B -> Audio-Offset {offset}")
    print(f"Audiotracks: {len(lengths)}  |  schneide {size - offset} B heraus")

    # 1. Audiobereich herausschneiden
    with open(args.bin, "rb") as src, open(binout, "wb") as dst:
        src.seek(offset)
        while (buf := src.read(CHUNK)):
            dst.write(buf)

    # 2. all-Audio-CUE schreiben (INDEX = laufende Summe der Track-Längen)
    lines, pos = ['FILE "audio-only.bin" BINARY'], 0
    for i, length in enumerate(lengths, start=1):
        lines += [f"  TRACK {i:02d} AUDIO", f"    INDEX 01 {frames_to_msf(pos)}"]
        pos += length
    with open(cueout, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"-> {binout}\n-> {cueout}")
    print("Weiter: bchunk -w audio-only.bin audio-only.cue track   (BIN muss little-endian sein)")

if __name__ == "__main__":
    main()
