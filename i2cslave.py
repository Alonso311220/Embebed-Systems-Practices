import machine 
from utime import sleep_ms, sleep_us
class I2CSlave():
    def __init__(self, id=0, address=0x27, sda=None, scl=None):
        if id > 1: raise ValueError("Unsupported")
        elif id == 0:
            if sda is None: sda = 0
            if scl is None: scl = 1
            if sda not in [0, 4, 8, 12, 16, 20]:
                raise ValueError("Invalid pin number for SDA")
            if scl not in [1, 5, 9, 13, 17, 21]:
                raise ValueError("Invalid pin number for scl")
        else:
            if sda is None: sda = 2
            if scl is None: scl = 3
            if sda not in [2, 6, 10, 14, 18, 26]:
                raise ValueError("Invalid pin number for SDA")
            if scl not in [3, 7, 11, 15, 19, 27]:
                raise ValueError("Invalid pin number for scl")
            
        if address < 0 or address > 0x7f:
            raise ValueError("Address out of range (7 bit addresses only)")
        self._sda = sda
        self._scl = scl
        self._addr = address
        self._base = __I2C0_BASE if id == 0 else __I2C1_BASE

        self.__setupPin(sda)
        self.__setupPin(scl)

        self.__regClr(__IC_ENABLE, 0X0001)

        self.__regClr(__IC_SAR, 0X01ff)
        self.__regSet(__IC_SAR, address)

        self.__regClr(__IC_CON, 0x0049)

        self.__regSet(__IC_ENABLE, 0X0001)
        self.__initialized = True

    def __setupPin(self, pin):
        gpioaddr = __IO_BANK0_BASE + 8 * pin + 4
        machine.mem32[ gpioaddr | __ATOM_CLR ] = 0x1f
        machine.mem32[ gpioaddr | __ATOM_SET ] = 0x03

    def __regClr(self, reg, mask):
        machine.mem32[self._base | __ATOM_CLR | reg] = mask

    def __regSet(self, reg, mask):
        machine.mem32[self._base | __ATOM_SET | reg] = mask

    def __regRead(self, reg, andmask=0xffffffff):
        return machine.mem32[self._base | __ATOM_RW | reg] & andmask

    def __regWrite(self, reg, value):
        machine.mem32[self._base | __ATOM_RW | reg] = value

    def __regXor(self, reg, mask):
        machine.mem32[self._base | __ATOM_XOR | reg] = mask

    @property
    def id(self):
        return 0 if self._base == __I2C0_BASE else 1

    @property
    def sda(self):
        return self._sda

    @property
    def scl(self):
        return self._scl

    @property
    def address(self):
        return self._addr

    def idle(self):
        return not self.__regRead(__IC_STATUS, 0x01)

    def rxBufferCount(self):
        return self.__regRead(__IC_RXFLR, 0x1f)

    def rxBufferEmpty(self):
        return not self.__regRead(__IC_STATUS, 0x08)

    def rxBufferFull(self):
        return self.__regRead(__IC_STATUS, 0x10)

    def txBufferCount(self):
        return self.__regRead(__IC_TXFLR, 0x10)

    def txBufferEmpty(self):
        return not self.__regRead(__IC_STATUS, 0x04)

    def txBufferFull(self):
        return not self.__regRead(__IC_STATUS, 0x02)

    def read(self):
        if not self.__initialized: raise IOError('Uninitialized')
        
        while not self.__regRead(__IC_STATUS, 0x08) and self.__regRead(__IC_RXFLR, 0x1f) < 1:
            sleep_us(10)
        
        bytecount = self.__regRead(__IC_RXFLR, 0x1f)
        ba = bytearray(bytecount)
        for i in range(bytecount):
            ba[i] = self.__regRead(__IC_DATA_CMD, 0xff)
        return ba

    def readByte(self):
        if not self.__initialized: raise IOError('Uninitialized')
        
        while not self.__regRead(__IC_STATUS, 0x08):
            sleep_us(10)
        
        return self.__regRead(__IC_DATA_CMD, 0xff)

    def write(self, ba):
        if not self.__initialized: raise IOError('Uninitialized')
        if not isinstance(ba, (bytes, bytearray)): 
            raise ValueError('An array of bytes is required')
        for b in ba:
            self.writeByte(b)

    def writeByte(self, b):
        if not self.__initialized: raise IOError('Uninitialized')
        
        while not self.__regRead(__IC_RAW_INTR_STAT, 0x20):
            sleep_us(10)
        
        self.__regClr(__IC_CLR_TX_ABRT, 0x01)
        self.__regRead(__IC_CLR_RD_REQ)
        
        while not self.__regRead(__IC_STATUS, 0x02):
            sleep_us(10)
        self.__regWrite(__IC_DATA_CMD, b & 0xff)

    def waitForData(self, timeout=-1):
        if not self.__initialized: raise IOError('Uninitialized')
        while self.rxBufferEmpty() and (timeout > 0):
            timeout -= 1
            sleep_ms(1)
        return not self.rxBufferEmpty()

    def waitForRdReq(self, timeout=-1):
        if not self.__initialized: raise IOError('Uninitialized')
        while (self.__regRead(__IC_RAW_INTR_STAT, 0x20) != 0) and (timeout > 0):
            timeout -= 1
            sleep_ms(1)
        return self.__regRead(__IC_RAW_INTR_STAT, 0x20)

