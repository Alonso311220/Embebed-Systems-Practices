import smbus2
import struct
import time

SLAVE_ADDR = 0x0A
i2c = smbus2.SMBus(1)

def write_power(power_pct: float) -> None:
    data = list(struct.pack('<f', float(power_pct)))
    msg  = smbus2.i2c_msg.write(SLAVE_ADDR, data)
    i2c.i2c_rdwr(msg)

def main():
    print("Control de intensidad de foco incandescente")
    print("Ingrese un valor de 0 a 100 (porcentaje de potencia)")
    print("Ctrl+C para salir\n")

    while True:
        try:
            raw   = input("Potencia [0-100]%: ").strip()
            power = float(raw)

            if not (0.0 <= power <= 100.0):
                print("Valor fuera de rango. Use 0-100.\n")
                continue

            write_power(power)
            print(f"Potencia enviada: {power:.1f}%\n")

        except ValueError:
            print("Entrada invalida. Ingrese un numero.\n")
        except KeyboardInterrupt:
            print("\nSaliendo...")
            write_power(0)
            break
        except Exception as e:
            print(f"Error I2C: {e}\n")
            time.sleep(0.5)

if __name__ == '__main__':
    main()
