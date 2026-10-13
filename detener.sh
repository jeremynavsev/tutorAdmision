#!/usr/bin/env bash
# Detiene el backend y el frontend que arrancó el entorno de desarrollo (flake.nix).
cd "$(dirname "$0")"
for nombre in backend frontend; do
  archivo=".dev/$nombre.pid"
  if [ -f "$archivo" ] && kill -0 "$(cat "$archivo")" 2>/dev/null; then
    # Cada servidor corre en su propio grupo de procesos (setsid): se detiene el grupo completo.
    kill -- -"$(cat "$archivo")" 2>/dev/null || kill "$(cat "$archivo")"
    echo "→ $nombre detenido."
  else
    echo "→ $nombre no estaba corriendo."
  fi
  rm -f "$archivo"
done
