#!/usr/bin/env python3
"""make_mp3_cue.py — CUE fuer DOSBox-X aus Daten-ISO + einzelnen Audiodateien.

Erzeugt das "iso/mp3"-Buendel: Track 01 = Daten-ISO (MODE1/2048), Track 02.. = je eine
Audiodatei. DOSBox-X spielt die FILE-Typen BINARY/WAVE/MP3/OGG/FLAC/AIFF.

Aufruf:  make_mp3_cue.py <data.iso> <audio_dir> [-o out.cue] [--ext mp3]
audio_dir: Ordner mit sortierbar benannten Audiodateien (z.B. track02.mp3, track03.mp3 ...).

Hinweis: ISO und alle Audiodateien muessen spaeter im SELBEN Ordner wie die CUE liegen
(die CUE referenziert nur Dateinamen, keine Pfade).
"""
import argparse, glob, os, sys

TYPE = {".mp3": "MP3", ".wav": "WAVE", ".flac": "FLAC", ".ogg": "OGG", ".aiff": "AIFF", ".aif": "AIFF"}

def main():
    ap = argparse.ArgumentParser(description="Daten-ISO + Audiodateien -> DOSBox-X-CUE")
    ap.add_argument("iso")
    ap.add_argument("audio_dir")
    ap.add_argument("-o", "--out")
    ap.add_argument("--ext", default="mp3", help="Audio-Endung (Default: mp3)")
    ap.add_argument("--rel", action="store_true",
                    help="Pfade relativ zum CUE-Ordner schreiben (erlaubt Audio in Unterordner)")
    args = ap.parse_args()

    files = sorted(glob.glob(os.path.join(args.audio_dir, f"*.{args.ext.lstrip('.')}")))
    if not files:
        sys.exit(f"FEHLER: keine *.{args.ext} in {args.audio_dir}")
    ftype = TYPE.get(os.path.splitext(files[0])[1].lower())
    if not ftype:
        sys.exit(f"FEHLER: Audiotyp nicht unterstuetzt ({', '.join(TYPE)}).")

    outpath = args.out or os.path.join(os.path.dirname(os.path.abspath(args.iso)),
                                       os.path.splitext(os.path.basename(args.iso))[0] + ".cue")
    cuedir = os.path.dirname(os.path.abspath(outpath))

    def ref(p):
        # relativer Pfad zum CUE-Ordner (--rel) bzw. nur Dateiname; immer mit "/"
        return os.path.relpath(os.path.abspath(p), cuedir).replace(os.sep, "/") if args.rel \
               else os.path.basename(p)

    lines = [f'FILE "{ref(args.iso)}" BINARY',
             "  TRACK 01 MODE1/2048", "    INDEX 01 00:00:00"]
    for i, f in enumerate(files, start=2):
        lines += [f'FILE "{ref(f)}" {ftype}',
                  f"  TRACK {i:02d} AUDIO", "    INDEX 01 00:00:00"]

    with open(outpath, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print(f"Geschrieben: {outpath}  (1 Daten + {len(files)} Audiotracks)")

if __name__ == "__main__":
    main()
