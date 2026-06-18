#!/usr/bin/env bash
# rename_image.sh — benennt einen Image-Satz im Ordner von <old> auf <new> um und passt
# die internen Datei-Referenzen in .toc/.cue an.
# Erfasst werden Dateien, deren Basisname mit "<old>" + Trenner ("." oder "-") beginnt:
#   game.bin game.toc game.cue game.iso game.bin.bak   -> tomb2.*
#   game-mp3.cue                                        -> tomb2-mp3.cue
# Nur der Praefix <old> wird getauscht; der Rest (Endung, "-mp3" usw.) bleibt.
# Referenzen, die NICHT mit "<old>." / "<old>-" beginnen (z.B. mp3/track02.mp3), bleiben unberuehrt.
#
# Aufruf: rename_image.sh <old> <new> [ordner]
#   z.B.:  rename_image.sh game tomb2
#
# Hinweis: DOSBox-Confs, die auf den alten Namen zeigen, ggf. von Hand anpassen.
set -euo pipefail
OLD="${1:?Aufruf: rename_image.sh <old> <new> [ordner]}"
NEW="${2:?Aufruf: rename_image.sh <old> <new> [ordner]}"
DIR="${3:-.}"
cd "$DIR"

shopt -s nullglob
files=( "$OLD".* "$OLD"-* )                    # <old>. ... UND <old>- ... (z.B. game-mp3.cue)
[ ${#files[@]} -gt 0 ] || { echo "Keine Dateien '$OLD.*' / '$OLD-*' in $(pwd)"; exit 1; }

for f in "${files[@]}"; do
  new="$NEW${f#"$OLD"}"                         # nur den Praefix <old> -> <new> tauschen
  [ -e "$new" ] && { echo "FEHLER: $new existiert bereits — abgebrochen."; exit 1; }
  mv -v -- "$f" "$new"
  case "$new" in
    *.toc|*.cue)                               # interne Referenzen "<old>." / "<old>-" anpassen
      sed -E "s/\"$OLD([.-])/\"$NEW\1/g" "$new" > "$new.tmp" && mv -- "$new.tmp" "$new"
      echo "  Referenzen \"$OLD\" -> \"$NEW\" in $new angepasst"
      ;;
  esac
done
echo "Fertig: $OLD -> $NEW in $(pwd)"
