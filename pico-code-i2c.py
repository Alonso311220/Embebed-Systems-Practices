from i2cslave import I2CSlave
from utime import sleep_ms, sleep_us
import machine
import ustruct

VAREF = 2.7273
I2C_SLAVE_ADDR = 0X0A

def main():
    setup()
    while True:
        #Get temperature in Celsius
        temperature = read_temp()
        #Convert temperature from pufloat to bytes
        data = unstruct.pack('< f', temperature)

        #Check if Master requested data
        if i2c.waitForRdReq(timeout = 0):
            #if so, send the temperature to Master
            i2c.write(data)
        #Check if Master sent data
        if i2c.waitForData(timeout = 0):
            #if so, print it
            rvc = i2c.read()
            print(rcv.decode('utf-8'))

def read_temp():
    #Read temperature en C from ADC
    return 25.0

def setup():
    global i2c, adcm, adcp
    i2c = I2CSlave(address=I2C_SLAVE_ADDR)
    adcm = machine.ADC(0)       #Init ADC0
    adcp = machine.ADC(1)       #Init ADC1

if __name__ == '__main__':
    main()
