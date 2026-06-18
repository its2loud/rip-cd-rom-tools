#!/usr/bin/env python3
"""swab_audio.py — Byteswap des Audiobereichs einer cdrdao-Mixed-Mode-BIN -> little-endian.

cdrdao schreibt CD-Audio als signed 16-bit BIG-endian. Standard-CUE/BIN und DOSBox-X
erwarten LITTLE-endian -> sonst Rauschen. Dieses Script tauscht jedes 16-bit-Sample-Paar
NUR im Audiobereich (ab dem Ende des Datentracks bis Dateiende); der Datentrack bleibt
unberuehrt. Verlustfrei reversibel (erneut laufen lassen = Original zurueck).

Den Audio-Start-Offset liest es AUTARK aus der cdrdao-.toc (DATAFILE-Laenge x
Sektorgroesse des Datentracks). Alternativ direkt per --offset.

Standardmaessig wird vorher ein Backup <bin>.bak angelegt (falls nicht vorhanden) und
in-place getauscht. Mit --no-backup wird ohne Backup getauscht (in-place, vorwaerts in
nicht-ueberlappenden Bloecken -> sicher, aber kein Undo ausser erneutem Lauf).

Aufruf:
  swab_audio.py <bin> <toc> [--no-backup]
  swab_audio.py <bin> --offset 234483712 [--no-backup]
"""
import argparse, os, re, shutil, sys
from array import array

CHUNK = 16 * 1024 * 1024  # 16 MiB, gerade -> 16-bit-ausgerichtet

# cdrdao-Datentrackmodus -> Sektorgroesse in Bytes
DATA_SECTOR = {"MODE1": 2048, "MODE1_RAW": 2352, "MODE2": 2336,
               "MODE2_RAW": 2352, "MODE2_FORM1": 2336}

def offset_from_toc(tocpath):
    text = open(tocpath, encoding="utf-8", errors="replace").read()
    mode = None
    for ln in text.splitlines():
        m = re.match(r'TRACK\s+(\S+)', ln.strip())
        if m and m.group(1).upper() != "AUDIO":
            mode = m.group(1).upper(); break
    if mode is None:
        sys.exit("FEHLER: kein Datentrack (TRACK MODE...) in der TOC gefunden.")
    if mode not in DATA_SECTOR:
        sys.exit(f"FEHLER: Datentrack-Modus {mode} nicht unterstuetzt ({', '.join(DATA_SECTOR)}).")
    m = re.search(r'DATAFILE\s+"[^"]*"\s+(?:#\d+\s+)?(\d+):(\d+):(\d+)', text)
    if not m:
        sys.exit("FEHLER: DATAFILE-Zeile mit Laenge nicht gefunden.")
    frames = (int(m[1]) * 60 + int(m[2])) * 75 + int(m[3])
    return frames * DATA_SECTOR[mode], mode, frames, DATA_SECTOR[mode]

def swap_in_place(path, offset):
    size = os.path.getsize(path)
    audio_len = size - offset
    done = 0
    with open(path, "r+b") as f:
        pos = offset
        while done < audio_len:
            f.seek(pos)
            chunk = f.read(min(CHUNK, audio_len - done))
            if not chunk:
                break
            a = array("H"); a.frombytes(chunk); a.byteswap()
            f.seek(pos); f.write(a.tobytes())
            pos += len(chunk); done += len(chunk)
            print(f"\r  {done}/{audio_len} Bytes ({100*done//audio_len}%)", end="", flush=True)
        f.flush(); os.fsync(f.fileno())
    print(f"\nFertig. {done} Bytes getauscht.")

def main():
    ap = argparse.ArgumentParser(description="Audiobereich einer Mixed-Mode-BIN byteswappen")
    ap.add_argument("bin", help="die zu tauschende .bin (in-place)")
    ap.add_argument("toc", nargs="?", help="cdrdao-.toc (fuer den Audio-Offset)")
    ap.add_argument("--offset", type=int, help="Audio-Start-Offset in Bytes (statt aus der .toc)")
    ap.add_argument("--no-backup", action="store_true", help="kein <bin>.bak anlegen")
    args = ap.parse_args()

    if args.offset is not None:
        offset = args.offset
        print(f"Audio-Offset: {offset} (per --offset)")
    elif args.toc:
        offset, mode, frames, sz = offset_from_toc(args.toc)
        print(f"Datentrack: {mode}, {frames} Frames x {sz} B -> Audio-Offset {offset}")
    else:
        sys.exit("FEHLER: entweder <toc> oder --offset angeben.")

    size = os.path.getsize(args.bin)
    if offset % 2 or (size - offset) % 2:
        sys.exit(f"FEHLER: Offset/Audiolaenge nicht 2-Byte-ausgerichtet (offset={offset}, size={size}).")
    if not (0 < offset < size):
        sys.exit(f"FEHLER: Offset {offset} liegt nicht innerhalb der Datei ({size} Bytes).")

    if args.no_backup:
        print("Kein Backup (--no-backup). Tausche in-place.")
    else:
        bak = args.bin + ".bak"
        if os.path.exists(bak):
            print(f"Backup vorhanden: {bak}")
        else:
            print(f"Lege Backup an: {bak} ...")
            shutil.copyfile(args.bin, bak)
    swap_in_place(args.bin, offset)

if __name__ == "__main__":
    main()
