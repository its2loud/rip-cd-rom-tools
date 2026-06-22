# Mixed-Mode-CDs (Daten + CD-Audio) rippen

Anleitung, um eine Spiele-CD mit Datentrack **und** CD-Audio (Redbook/CDDA) so
aufzubereiten, dass sie in DOSBox-X inkl. Musik läuft. Zwei Varianten:

- **BIN/CUE** — ein Image mit Daten- und Audiotracks, per CUE gemountet.
- **ISO/MP3** — Daten-ISO + einzelne MP3s, per CUE gebündelt (platzsparend).

cdrdao legt CD-Audio in der falschen Byte-Reihenfolge ab
(16-bit **big-endian** statt **little-endian**)
cdrdaos:
> „[…] wenn die toc-Datei Audiotracks enthält, ist die Byte-Reihenfolge der
> Image-Datei falsch, was zu statischem Rauschen führt, sobald die resultierende
> cue-Datei verwendet wird (sogar mit cdrdao selbst)."
`swab_audio.py` dreht den Audiobereich auf little-endian; der Datentrack bleibt.

---

## Voraussetzungen / Installation

**Linux-Box (Rippen + Audio)** — Debian/Mint:
```bash
sudo apt install cdrdao cdparanoia libcdio-utils bchunk ffmpeg python3
sudo apt install gddrescue
```
`cdrdao` (rippt + bringt `toc2cue` mit) · `cdparanoia` (Audio→WAV, listet auch die Tracks) ·
`bchunk` (BIN→Tracks) · `ffmpeg` (WAV→MP3) · `python3` (für scripts) · `libcdio-utils` (für cd-info/ tracks), `gddrescue` (sicheres dd).

---

## Laufwerk finden und CD-Typ bestimmen

```bash
# Welche optischen Laufwerke gibt es?
ls -l /dev/sr* /dev/cdrom* 2>/dev/null
# Laufwerksliste + Fähigkeiten
cat /proc/sys/dev/cdrom/info
# Report mit Trackdaten
cd-info /dev/sr0

# Hat die CD ueberhaupt Audiotracks? (sonst reicht eine reine ISO, kein swab noetig)
# listet die Audiotracks (keine -> reine Daten-CD)
cdparanoia -Q -d /dev/sr0

mount | grep sr
sudo umount /dev/sr0
```
- **Nur ein Datentrack** → einfache ISO
- **Datentrack + Audiotracks** → Mixed-Mode Bundles


Im Folgenden ist `/dev/sr0` das Laufwerk und `game` der Basisname — anpassen.

---

## ISO von Daten CD
```bash
cd-info /dev/sr0          # "CD-DATA (Mode 1)" + genau ein data-Track?
isoinfo -d -i /dev/sr0    # liefert "Volume size is: <BLOCKS>" (in 2048er-Blöcken)

# Empfohlen
# -b 2048 = Sektorgröße, -r3 = 3 Wiederholungen
sudo ddrescue -b 2048 -r3 /dev/sr0 game.iso ddrescue.mapfile
# --direct und --reverse bei fehlerhaften Sektoren
sudo ddrescue -d -R -b 2048 -r3 /dev/sr0 game.iso ddrescue.mapfile

# Alternative mit dd
N=$(isoinfo -d -i /dev/sr0 | awk '/Volume size is:/{print $4}')
sudo dd if=/dev/sr0 of=game.iso bs=2048 count="$N" status=progress

# Verifizieren
isoinfo -d -i game.iso                       # plausible Volume size / Label?
sudo mount -o loop,ro game.iso /mnt && ls -la /mnt && sudo umount /mnt
```

## Bundle BIN/CUE (von der CD)

```bash
# 1. Rippen MIT --read-raw -> alle Tracks 2352 B/Sektor (gleichmaessig). Das macht die BIN
#    DOSBox-tauglich UND spaeter mit Standard-Tools (bchunk) zerlegbar (siehe unten).
cdrdao read-cd --read-raw --datafile game.bin --device /dev/sr0 --driver generic-mmc-raw game.toc
#    Variante OHNE --read-raw:
#    cdrdao read-cd --datafile game.bin --device /dev/sr0 --driver generic-mmc game.toc

# 2. CUE aus der cdrdao-TOC -> TRACK 01 MODE1/2352.
toc2cue game.toc game.cue

# 3. Audio big->little-endian. Offset wird aus game.toc gelesen; legt game.bin.bak an.
python3 swab_audio.py game.bin game.toc
#    ohne Backup: 
#    python3 swab_audio.py game.bin game.toc --no-backup
```
**Ergebnis:** `game.cue` + `game.bin` (LE).
Backup `game.bin.bak` kann nach erfolgreichem Test gelöscht werden.

---

## Optional — MP3s aus der vorhandenen BIN (ohne CD)

**Voraussetzung:** mit `--read-raw` gerippt
(gleichmäßige 2352-Sektoren) und `game.bin` bereits **little-endian** oder bchunk mit -s.

```bash
bchunk -w game.bin game.cue track     # track01 = Daten (.iso), track02+ = Audio (.wav)
for w in track*.wav; do ffmpeg -y -i "$w" -q:a 2 "${w%.wav}.mp3"; done
```
bchunks `-s` swappt die Audio-Byte-Order selbst, wenn die BIN *nicht* geswabbt ist

---

## Bundle ISO/MP3 (von der CD)

```bash
# 1. Daten-ISO exakt auslesen. Blockzahl = ISO9660-"Volume Space Size" aus dem PVD
#    (Sektor 16, Byte 80, 32-bit little-endian):
# 	N=$(dd if=/dev/sr0 bs=2048 skip=16 count=1 2>/dev/null | od -An -tu4 -j80 -N4 | tr -d ' ')
# 	dd if=/dev/sr0 of=game.iso bs=2048 count="$N"

sudo ddrescue -b 2048 -r3 /dev/sr0 game.iso ddrescue.mapfile

# 2. Audio verlustlos als WAV -> MP3 (cdparanoia liefert korrekte Byte-Order, kein swab).
mkdir -p mp3
cdparanoia -B -d /dev/sr0                          # track02.cdda.wav, track03.cdda.wav, ...
for w in track*.cdda.wav; do ffmpeg -y -i "$w" -q:a 2 "mp3/${w%.cdda.wav}.mp3"; done

# 3. CUE bauen (--rel erlaubt die MP3s im Unterordner mp3/; Default-Ausgabe: game.cue).
python3 make_mp3_cue.py game.iso mp3/ --rel
```
**Ergebnis:** `game.iso` + `mp3/*.mp3` + `game.cue`.

---

## Cleanup

Beispiel `game` → `tomb2`:
```bash
rm game.bin.bak                    # swab-Backup (BIN/CUE)
rm -f track*.cdda.wav              # WAVs von cdparanoia (ISO/MP3)
rm ddrescue.mapfile                # ddrescue Protokoll
bash rename_image.sh game tomb2    # game.* -> tomb2.* inkl. Referenzen in .toc/.cue
```
> Im jeweiligen Bundle-Ordner ausführen.

---

## Tools

| Script | Zweck |
|---|---|
| `swab_audio.py <bin> <toc> [--no-backup]` | Audiobereich big→little-endian; Offset aus .toc. |
| `make_mp3_cue.py <iso> <audio_dir> [--rel]` | Daten-ISO + Audiodateien → CUE (MP3/WAV/FLAC/OGG/AIFF). |
| `carve_audio.py <bin> <toc> [-o dir]` | Für 2048er-Images (ohne --read-raw): Audiobereich → `audio-only.bin` + all-Audio-CUE für bchunk. |
| `rename_image.sh <old> <new> [ordner]` | Benennt `<old>.*` und `<old>-*` → `<new>…` im Ordner und passt die Referenzen in `.toc`/`.cue` an. |

---

## Anhang

### `--read-raw`: mit vs. ohne

| | **mit `--read-raw`** (Daten 2352/Sektor) | **ohne `--read-raw`** (Daten 2048/Sektor) |
|---|---|---|
| Sektorgröße | durchgängig 2352 (gleichmäßig) | gemischt: Daten 2048, Audio 2352 |
| Größe | größer (Daten ~+15 %) | kleiner |
| ISO ziehen | 1 Befehl: `bchunk … track` → `track01.iso` (Anhang B) | 1 Befehl: `dd bs=2048` |
| Audio per bchunk aus der BIN | direkt (`bchunk -w`, Byteswap via `-s`) | mittels carve |
| Archiv-Treue | bit-exakte 1:1-Kopie (Sync/Header/ECC) | nur Nutzdaten |
| Kopierschutz / Lesefehler | Rohsektoren (Sync/ECC/EDC) erfasst → nötig für viele Kopierschutze, robuster bei beschädigten Discs/Preservation | nur fehlerkorrigierte Nutzdaten, Rohinfo verloren |
| DOSBox-X | spielt (MODE1/2352) | spielt (MODE1/2048) |
| Byteswap | ja (`swab_audio.py`) | ja (`swab_audio.py`) |

**Empfehlung:** `--read-raw` — 1:1-Kopie fürs Archiv, DOSBox-tauglich, und Audio **wie auch**
ISO fallen mit je einem bchunk-Aufruf heraus. (ISO-Detail: Anhang B.)

**Warum scheitert bchunk ohne `--read-raw`?** Am bchunk-Quellcode verifiziert: bchunk kennt
`MODE1/2048` gar nicht und rechnet Track-Offsets immer mit festem 2352
(`track->start = startsect * SECTLEN`, `SECTLEN = 2352`). Nach einem 2048er-Datentrack
liegt der Audio-Anfang damit falsch → korrupte Tracks. Ausweg nur über Carve
(`carve_audio.py`, Anhang C).

### ISO aus einem `--read-raw`-Rip ziehen (2352 → 2048)

Der Raw-Datentrack ist 2352 B/Sektor, eine ISO ist 2048. bchunk strippt Sync/Header/ECC
beim Zerlegen automatisch — der Datentrack landet als saubere ISO in `track01`:

```bash
bchunk game.bin game.cue track    # ohne -w
# -> track01.iso  (Datentrack als 2048er-ISO; track02+ = Audiotracks als .cdr)
```
(Mit `-w` kommen die Audiotracks als WAV; `track01.iso` entsteht so oder so.)

### Audio aus einem Image OHNE `--read-raw` (Script `carve_audio.py`)

bchunk scheitert an der gemischten Sektorgröße (Anhang A). `carve_audio.py` löst das:
es schneidet den Audiobereich heraus (→ `audio-only.bin`, uniform 2352) und schreibt die
passende all-Audio-CUE (→ `audio-only.cue`); Offset und Trackgrenzen liest es aus der
`.toc`. Voraussetzung: `game.bin` ist bereits **little-endian** (swab gelaufen).

```bash
python3 carve_audio.py game.bin game.toc         # -> audio-only.bin + audio-only.cue
bchunk -w audio-only.bin audio-only.cue track    # track01.wav, track02.wav, ...
for w in track*.wav; do ffmpeg -y -i "$w" -q:a 2 "${w%.wav}.mp3"; done
```

