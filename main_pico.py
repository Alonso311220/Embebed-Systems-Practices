import machine
from i2cslave import I2CSlave
from utime import sleep_ms, ticks_ms, ticks_diff
import ustruct

VAREF = 3.3
OFFSET_DIODOS = 1.2
I2C_SLAVE_ADDR = 0x37

def read_temp():
    raw = adc.read_u16()
    voltaje = (raw * VAREF) / 65535.0
    return (voltaje - OFFSET_DIODOS) * 100.0

def setup():
    global i2c, adc
    machine.Pin(23, machine.Pin.OUT).value(1)
    i2c = I2CSlave(id=0, address=I2C_SLAVE_ADDR)
    adc = machine.ADC(0)

def main():
    setup()
    print(f"Pico lista en {hex(I2C_SLAVE_ADDR)}...")
    
    # Tomamos UNA lectura inicial antes de entrar al loop
    current_temp = read_temp()
    data = ustruct.pack('<f', current_temp)
    last_update = ticks_ms()

    while True:
        try:
            # escuchamos I2C con un timeout grande
            if i2c.waitForRdReq(timeout=200):
                i2c.write(data)
                print(f"Enviado: {current_temp:.2f}°C")

            # solo actualizamos temperatura si ya pasó 1 segundo sin estar en medio de una transacción I2C
            if ticks_diff(ticks_ms(), last_update) > 1000:
                current_temp = read_temp()  
                data = ustruct.pack('<f', current_temp)
                print(f"Temp actualizada: {current_temp:.2f}°C")
                last_update = ticks_ms()

        except Exception as e:
            print(f"Error I2C: {e}, reiniciando esclavo...")
            sleep_ms(100)
            i2c = I2CSlave(id=0, address=I2C_SLAVE_ADDR)

        sleep_ms(1)

if __name__ == '__main__':
    main()
