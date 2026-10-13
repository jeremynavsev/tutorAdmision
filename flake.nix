{
  description = "MAEstro - Entorno de desarrollo";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
      in
      {
        devShells.default = pkgs.mkShell {
          name = "maestro-dev";

          packages = with pkgs; [
            # Backend - Python / FastAPI
            python312

            # Frontend - Next.js
            nodejs_22

            # Herramientas
            git
            curl
            jq
          ];

          shellHook = ''
            RAIZ="$PWD"
            LOGS="$RAIZ/.dev/logs"
            mkdir -p "$LOGS"

            # Indica si un puerto ya tiene un proceso escuchando.
            puerto_ocupado() { ss -ltnH "sport = :$1" 2>/dev/null | grep -q .; }

            # Indica si el proceso guardado en .dev/<nombre>.pid sigue vivo.
            corriendo() { [ -f "$RAIZ/.dev/$1.pid" ] && kill -0 "$(cat "$RAIZ/.dev/$1.pid")" 2>/dev/null; }

            echo ""
            echo "MAEstro · entorno de desarrollo"
            echo "==============================="
            echo "  Python : $(python3.12 --version)"
            echo "  Node   : $(node --version)"
            echo ""

            # 1) Backend: crea el .venv la primera vez y arranca uvicorn.
            if [ ! -x backend/.venv/bin/uvicorn ]; then
              echo "→ Creando backend/.venv e instalando dependencias (solo la primera vez)..."
              PIP_DISABLE_PIP_VERSION_CHECK=1 python3.12 -m venv backend/.venv \
                && PIP_DISABLE_PIP_VERSION_CHECK=1 backend/.venv/bin/pip install -q -r backend/requirements-dev.txt \
                || echo "  Aviso: falló la instalación del backend."
            fi
            if corriendo backend; then
              echo "→ Backend ya está corriendo."
            elif puerto_ocupado 8100; then
              echo "→ Aviso: el puerto 8100 está ocupado por otro programa. Backend no iniciado."
            elif [ -x backend/.venv/bin/uvicorn ]; then
              echo "→ Iniciando backend en http://localhost:8100"
              # Se cierran los descriptores heredados: direnv lee el entorno por el 3 y, si
              # el servidor se lo queda abierto, direnv espera para siempre y la terminal se pega.
              (exec 3>&- 4>&- 5>&- 6>&- 7>&- 8>&- 9>&-; cd backend || exit; setsid nohup .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8100 \
                > "$LOGS/backend.log" 2>&1 < /dev/null & echo $! > "$RAIZ/.dev/backend.pid")
            fi

            # 2) Frontend: instala node_modules la primera vez y arranca next dev.
            if [ ! -d web/node_modules ]; then
              echo "→ Instalando dependencias del frontend (solo la primera vez)..."
              (cd web && npm ci --silent) || echo "  Aviso: falló npm ci."
            fi
            if corriendo frontend; then
              echo "→ Frontend ya está corriendo."
            elif puerto_ocupado 3100; then
              echo "→ Aviso: el puerto 3100 está ocupado por otro programa. Frontend no iniciado."
            elif [ -d web/node_modules ]; then
              echo "→ Iniciando frontend en http://localhost:3100"
              # Se cierran los descriptores heredados: direnv lee el entorno por el 3 y, si
              # el servidor se lo queda abierto, direnv espera para siempre y la terminal se pega.
              (exec 3>&- 4>&- 5>&- 6>&- 7>&- 8>&- 9>&-; cd web || exit; setsid nohup npx next dev -p 3100 \
                > "$LOGS/frontend.log" 2>&1 < /dev/null & echo $! > "$RAIZ/.dev/frontend.pid")
            fi

            unset -f puerto_ocupado corriendo

            echo ""
            echo "Logs:     tail -f .dev/logs/backend.log .dev/logs/frontend.log"
            echo "Detener:  ./detener.sh"
            echo ""
          '';
        };
      });
}
