import smbus2
import struct
import time

SLAVE_ADDR = 0x37
LOG_FILE = './temp.log'
BUS = 1  # GPIO3=SDA, GPIO5=SCL

def get_temp(i2c):
    for intento in range(5):
        try:
            # leeyendo bytes crudos directamente sin enviar un byte de registro primero.
            msg = smbus2.i2c_msg.read(SLAVE_ADDR, 4)
            i2c.i2c_rdwr(msg)
            
            raw = bytes(msg)
            temp = struct.unpack('<f', raw)[0]
            
            # descartar valores
            if -40.0 <= temp <= 150.0:
                return temp
            else:
                print(f"Valor fuera de rango descartado: {temp:.2f}°C")
                
        except Exception as e:
            print(f"Intento {intento+1}/5 fallido: {e}")
            time.sleep(0.2)
            
    return None

def log_temp(temperature):
    if temperature is None:
        return
    try:
        with open(LOG_FILE, 'a') as fp:
            # Sin "°C" en el log para que graficar_historico.py lo parsee bien
            fp.write(f'{time.time():.3f} {temperature:.2f}\n')
        print(f"Registrado: {temperature:.2f}°C")
    except Exception as e:
        print(f"Error escribiendo log: {e}")

def main():
    print("Iniciando lectura I2C...")
    try:
        i2c = smbus2.SMBus(BUS)
        print(f"Bus I2C {BUS} abierto. Leyendo esclavo {hex(SLAVE_ADDR)}...")
    except Exception as e:
        print(f"No se pudo abrir el bus I2C: {e}")
        return

    print("Recolectando datos (Ctrl+C para cerrar)...")
    try:
        while True:
            temp = get_temp(i2c)
            log_temp(temp)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nDetenido por el usuario.")
    finally:
        i2c.close() #cerrando el bus

if __name__ == '__main__':
    main()