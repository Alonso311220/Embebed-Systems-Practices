import smbus2
import struct
import time

# RP2040 I2C device address
SLAVE_ADDR = 0x0A

# Name of the file in which the log is kept
LOG_FILE = './temp.log'

# Initialize the I2C bus; RPI version 1 requires smbus.SMBus(0)
i2c = smbus2.SMBus(1)

def readTemperature():
    try:
        msg = smbus2.i2c_msg.read(SLAVE_ADDR, 4)
        i2c.i2c_rdwr(msg) # Performs write (read request)
        
        data = list(msg) # Converts stream to list
        
        # List to array of bytes (más eficiente)
        ba = bytearray(data) 
        
        # unpack devuelve una tupla, agregamos [0] para sacar el número
        temp = struct.unpack('<f', ba)[0] 
        
        # Imprimir a consola con formato más limpio
        print(f'Bytes recibidos: {data} = {temp:.2f} °C')
        
        return temp
    except Exception as e:
        print(f"Error de comunicación I2C: {e}")
        return None

def log_temp(temperature):
    # Si la lectura falló, no guardamos nada en la bitácora
    if temperature is None:
        return
        
    try:
        # CRÍTICO: Usar 'a' (append) para no borrar el histórico
        with open(LOG_FILE, 'a') as fp:
            fp.write(f'{time.time()} {temperature:.2f} °C\n')
    except Exception as e:
        print(f"Error al escribir en bitácora: {e}")

def main():
    print("Iniciando lectura I2C (Maestro)...")
    while True:
        try:
            cTemp = readTemperature()
            log_temp(cTemp)
            time.sleep(1)
        except KeyboardInterrupt:
            print("\nLectura detenida por el usuario.")
            break

if __name__ == '__main__':
    main()