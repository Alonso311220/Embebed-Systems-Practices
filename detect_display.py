"""
Detecta qué driver de video funciona en esta Pi.
Corre: python3 detect_display.py
"""
import os, subprocess, sys

print("\n=== DETECCION DE DISPLAY ===\n")

# 1. Dispositivos disponibles
print("-- Dispositivos de video:")
for dev in ["/dev/fb0", "/dev/fb1", "/dev/dri/card0", "/dev/dri/card1"]:
    exists = os.path.exists(dev)
    if exists:
        perm = oct(os.stat(dev).st_mode)[-3:]
        print(f"  {dev}  EXISTS  permisos={perm}")
    else:
        print(f"  {dev}  NO existe")

# 2. Grupos del usuario actual
print("\n-- Grupos del usuario:")
try:
    out = subprocess.check_output(["groups"], text=True).strip()
    print(f"  {out}")
    if "video" in out: print("  => grupo 'video': SI")
    else:              print("  => grupo 'video': NO (puede causar problemas)")
except: pass

# 3. Variables de entorno actuales
print("\n-- Variables SDL/DISPLAY:")
for v in ["SDL_VIDEODRIVER","SDL_FBDEV","DISPLAY","XAUTHORITY"]:
    print(f"  {v}={os.environ.get(v,'(no definida)')}")

# 4. Intentar cada driver
print("\n-- Probando drivers SDL:")
drivers = ["fbdev", "directfb", "offscreen", "dummy"]

for drv in drivers:
    os.environ["SDL_VIDEODRIVER"] = drv
    if drv == "fbdev":
        os.environ["SDL_FBDEV"] = "/dev/fb0"
    try:
        import pygame
        pygame.display.init()
        info = pygame.display.Info()
        print(f"  {drv:12s} => OK  ({info.current_w}x{info.current_h})")
        pygame.display.quit()
    except Exception as e:
        print(f"  {drv:12s} => FALLO: {e}")

# 5. Revisar si hay consola framebuffer activa
print("\n-- Estado del framebuffer:")
try:
    out = subprocess.check_output(["fbset", "-s"], text=True, stderr=subprocess.DEVNULL)
    print(out.strip())
except:
    print("  fbset no disponible o sin framebuffer")

print("\n-- /proc/fb:")
try:
    print(open("/proc/fb").read().strip() or "  (vacio)")
except:
    print("  no disponible")

print()