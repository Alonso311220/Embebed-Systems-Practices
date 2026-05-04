import os
import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
 
# ── Importar funciones del módulo maestro ────────────────────
from act3_raspberry_master import (
    write_power,
    read_confirmation,
    calcular_potencia_real,
    VOLTAJE,
    area_lut,
)
 
# ── Configuración del servidor ───────────────────────────────
HOST = "0.0.0.0"
PORT = 8080
 
# Directorio base: donde vive este script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
 
# Estado interno (última lectura exitosa)
_last_status: dict = {}
 
 
# ════════════════════════════════════════════════════════════
#  Helpers
# ════════════════════════════════════════════════════════════
 
MIME_TYPES = {
    ".html": "text/html",
    ".js":   "application/javascript",
    ".css":  "text/css",
    ".json": "application/json",
    ".ico":  "image/x-icon",
}
 
def mime_for(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    return MIME_TYPES.get(ext, "application/octet-stream")
 
 
def _aplicar_potencia(power_pct: float) -> dict:
    """
    Envía la potencia al RP2040, espera confirmación y devuelve
    el mismo diccionario de datos que imprime act3_raspberry_master.
    """
    write_power(power_pct)
    time.sleep(0.05)                     # margen de respuesta I2C
    confirmado = read_confirmation()
 
    if confirmado < 0:
        return {"ok": False, "error": "Error reportado por RP2040"}
 
    power_int      = int(confirmado)
    p_real, t_ms   = calcular_potencia_real(power_int)
    p_max          = round((VOLTAJE ** 2) * area_lut[0], 1)
    p_pct_real     = round((p_real / p_max) * 100, 1)
 
    resultado = {
        "ok":             True,
        "voltaje":        VOLTAJE,
        "power_solicitado": round(power_pct, 1),
        "power_aplicado": power_int,
        "tiempo_ms":      t_ms,
        "potencia_w":     p_real,
        "potencia_max_w": p_max,
        "potencia_pct":   p_pct_real,
    }
    global _last_status
    _last_status = resultado
    return resultado
 
 
# ════════════════════════════════════════════════════════════
#  Handler HTTP
# ════════════════════════════════════════════════════════════
 
class WebHandler(BaseHTTPRequestHandler):
 
    # ── Silencia los logs de cada request ───────────────────
    def log_message(self, format, *args):
        pass
 
    # ────────────────────────────────────────────────────────
    #  Utilidades de respuesta
    # ────────────────────────────────────────────────────────
 
    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type",   "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)
 
    def _send_file(self, filepath: str):
        """Sirve un archivo estático desde el filesystem."""
        if not os.path.isfile(filepath):
            self._send_json({"error": "Archivo no encontrado"}, 404)
            return
        with open(filepath, "rb") as f:
            content = f.read()
        self.send_response(200)
        self.send_header("Content-Type",   mime_for(filepath))
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)
 
    def _parse_path(self):
        """Devuelve la ruta sin query-string."""
        return self.path.split("?")[0]
 
    # ────────────────────────────────────────────────────────
    #  GET
    # ────────────────────────────────────────────────────────
 
    def do_GET(self):
        path = self._parse_path()
 
        # ── Página principal ─────────────────────────────────
        if path in ("/", "/PaginaGrafica.html"):
            self._send_file(os.path.join(BASE_DIR, "PaginaGrafica.html"))
            return
 
        # ── Archivos estáticos js/ y css/ ────────────────────
        if path.startswith("/js/") or path.startswith("/css/"):
            # Quitar la barra inicial para construir ruta relativa
            rel = path.lstrip("/")                      # ej. "js/jquery.min.js"
            self._send_file(os.path.join(BASE_DIR, rel))
            return
 
        # ── Estado actual (última potencia aplicada) ─────────
        if path == "/read_status":
            if _last_status:
                self._send_json(_last_status)
            else:
                self._send_json({"ok": False, "error": "Sin lecturas previas"}, 404)
            return
 
        self._send_json({"error": "Ruta no encontrada"}, 404)
 
    # ────────────────────────────────────────────────────────
    #  POST
    # ────────────────────────────────────────────────────────
 
    def do_POST(self):
        path = self._parse_path()
 
        # ── Aplicar potencia al foco ──────────────────────────
        if path == "/set_power":
            length   = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length)
 
            try:
                payload   = json.loads(raw_body.decode("utf-8"))
                power_pct = float(payload.get("power", 0))
                power_pct = max(0.0, min(100.0, power_pct))   # clamp 0-100
            except (ValueError, KeyError) as exc:
                self._send_json({"ok": False, "error": f"JSON inválido: {exc}"}, 400)
                return
 
            try:
                resultado = _aplicar_potencia(power_pct)
                self._send_json(resultado)
                print(f"[set_power] {power_pct:.1f}% → "
                      f"{resultado.get('potencia_w', '?')} W  "
                      f"({resultado.get('tiempo_ms', '?')} ms)")
            except Exception as exc:
                self._send_json({"ok": False, "error": f"Error I2C: {exc}"}, 500)
            return
 
        self._send_json({"error": "Ruta no encontrada"}, 404)
 
    # ────────────────────────────────────────────────────────
    #  OPTIONS  (CORS preflight, por si el browser lo pide)
    # ────────────────────────────────────────────────────────
 
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin",  "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
 
 
# ════════════════════════════════════════════════════════════
#  Punto de entrada
# ════════════════════════════════════════════════════════════
 
def main():
    server = HTTPServer((HOST, PORT), WebHandler)
    print("=" * 50)
    print(" Control de foco incandescente")
    print(f"  Escuchando en  http://{HOST}:{PORT}")
    print(f"  Front-end  ->   http://localhost:{PORT}/")
    print("  Ctrl+C para detener")
    print("=" * 50)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Apagando el foco y cerrando servidor...")
        try:
            write_power(0)           # apagado de seguridad
        except Exception:
            pass
        server.server_close()
        print("Servidor detenido ):")
 
 
if __name__ == "__main__":
    main()
