#!/usr/bin/python3

import gatt
import uinput
import signal
import math
import time
import numpy as np
import sys
import os

manager = gatt.DeviceManager(adapter_name='hci0')

class AnyDevice(gatt.Device):
    def connect_succeeded(self):
        super().connect_succeeded()
        print("[%s] Connected" % (self.mac_address))

    def connect_failed(self, error):
        super().connect_failed(error)
        print("[%s] Connection failed: %s" % (self.mac_address, str(error)))

    def disconnect_succeeded(self):
        super().disconnect_succeeded()
        print("[%s] Disconnected" % (self.mac_address))
        sys.exit(0)

    def write(self, cmd, times):
        for i in range(times - 1):
            self.__setup_characteristic.write_value(cmd)

    def services_resolved(self):
        super().services_resolved()

        controller_data_service = next(
            s for s in self.services
            if s.uuid == '4f63756c-7573-2054-6872-65656d6f7465')

        controller_setup_data_characteristic = next(
            c for c in controller_data_service.characteristics
            if c.uuid == 'c8c51726-81bc-483b-a052-f7a14ea3d282')

        controller_data_characteristic = next(
            c for c in controller_data_service.characteristics
            if c.uuid == 'c8c51726-81bc-483b-a052-f7a14ea3d281')

        self.__setup_characteristic = controller_setup_data_characteristic
        self.__sensor_characteristic = controller_data_characteristic

        #bad 8678 8768 8761
        # good  0 -> 8761(bad) -(?)> 1678 (ok)

        self.write(bytearray(b'\x01\x00'), 3)
        #self.write(bytearray(b'\x05\x00'), 1)
        self.write(bytearray(b'\x06\x00'), 1)
        self.write(bytearray(b'\x07\x00'), 1)
        self.write(bytearray(b'\x08\x00'), 3)

        self.__max = 315
        self.__r = self.__max / 2
        self.__axisX = self.__axisY = 0
        self.__altX = self.__altY = 0
        self.__device = uinput.Device([uinput.REL_X, uinput.REL_Y, uinput.BTN_LEFT, uinput.BTN_RIGHT, uinput.KEY_LEFTCTRL, uinput.KEY_LEFTALT, uinput.KEY_HOME, uinput.KEY_UP, uinput.KEY_DOWN, uinput.KEY_LEFT, uinput.KEY_RIGHT, uinput.KEY_VOLUMEUP, uinput.KEY_VOLUMEDOWN, uinput.KEY_KPPLUS, uinput.KEY_KPMINUS, uinput.KEY_PAGEUP, uinput.KEY_PAGEDOWN, uinput.KEY_KP0, uinput.KEY_SCROLLDOWN, uinput.KEY_SCROLLUP ]) # , uinput.BTN_TOUCH, uinput.ABS_PRESSURE

        self.__reset = self.__volbtn = self.__tchbtn = self.__trig = True

        self.__time = round(time.time()) + 10
        self.__lastupdated = 0
        self.__updatecounts = 0
        self.__VR = False

        controller_data_characteristic.enable_notifications()
        print("setup done")

    def keepalive(self):
        # test time and each minute send a keepalive
        if (time.time() > self.__time):
            self.__time = round(time.time()) + 10
            cmd = bytearray(b'\x04\x00')
            for i in range(4):
                self.__setup_characteristic.write_value(cmd)

    def characteristic_value_updated(self, characteristic, value):
        if (characteristic == self.__sensor_characteristic):
            if self.__VR == False:
                self.__updatecounts += 1
                if self.__updatecounts == 20:
                    now = time.time()
                    self.__updatecounts = 0
                    deltatime = now - self.__lastupdated
                    self.__lastupdated = now
                    if deltatime > 0.23:
                        #print("VR mode needs activation ", deltatime)
                        #self.write(bytearray(b'\x05\x00'), 1)
                        self.write(bytearray(b'\x06\x00'), 1)
                        self.write(bytearray(b'\x08\x00'), 3)
                        self.write(bytearray(b'\x07\x00'), 1)
                    else:
                        print("VR mode enabled ", deltatime)
                        self.__VR = True

            self.keepalive()
            int_values = [x for x in value]
            if (len(int_values) < 60):
                self.__VR = True
                #print("Value vector too short: ", len(int_values), " ", value, " VR mode is activated")
                print("VR mode is activated")
                self.write(bytearray(b'\x01\x00'), 3)
                self.__sensor_characteristic.enable_notifications()
                return

            axisX = (((int_values[54] & 0xF) << 6) + ((int_values[55] & 0xFC) >> 2)) & 0x3FF
            axisY = (((int_values[55] & 0x3) << 8) + ((int_values[56] & 0xFF) >> 0)) & 0x3FF
            accelX  = np.uint16((int_values[4]  << 8) + int_values[5])  * 10000.0 * 9.80665 / 2048.0
            accelY  = np.uint16((int_values[6]  << 8) + int_values[7])  * 10000.0 * 9.80665 / 2048.0
            accelZ  = np.uint16((int_values[8]  << 8) + int_values[9])  * 10000.0 * 9.80665 / 2048.0
            gyroX   = np.uint16((int_values[10] << 8) + int_values[11]) * 10000.0 * 0.017453292 / 14.285
            gyroY   = np.uint16((int_values[12] << 8) + int_values[13]) * 10000.0 * 0.017453292 / 14.285
            gyroZ   = np.uint16((int_values[14] << 8) + int_values[15]) * 10000.0 * 0.017453292 / 14.285
            magnetX = np.uint16((int_values[32] << 8) + int_values[33]) * 0.06
            magnetY = np.uint16((int_values[34] << 8) + int_values[35]) * 0.06
            magnetZ = np.uint16((int_values[36] << 8) + int_values[37]) * 0.06

            triggerButton    = True if ((int_values[58] &  1) ==  1) else False
            homeButton       = True if ((int_values[58] &  2) ==  2) else False
            backButton       = True if ((int_values[58] &  4) ==  4) else False
            touchpadButton   = True if ((int_values[58] &  8) ==  8) else False
            volumeUpButton   = True if ((int_values[58] & 16) == 16) else False
            volumeDownButton = True if ((int_values[58] & 32) == 32) else False
            NoButton         = True if ((int_values[58] & 64) == 64) else False

            idelta = 30
            odelta = 25

            if (triggerButton == True and self.__trig == True):
                self.__device.emit(uinput.BTN_LEFT, 1)
                self.__trig = False
            elif (triggerButton == False and self.__trig == False):
                self.__device.emit(uinput.BTN_LEFT, 0)

            outerCircle = True if (axisX - self.__r)**2 + (axisY - self.__r)**2 > (self.__r - odelta)**2  else False
            T = True if (outerCircle and axisY != 0 and axisY < odelta) else False              # Top
            B = True if (outerCircle and axisY != 0 and axisY > self.__max - odelta) else False # Bottom
            L = True if (outerCircle and axisX != 0 and axisX < odelta) else False              # Left
            R = True if (outerCircle and axisY != 0 and axisX > self.__max - odelta) else False # Right

            if (touchpadButton == True):
                if (T and self.__tchbtn == True):
                    for i in range(4):
                        self.__device.emit(uinput.KEY_UP, 1, syn = True)
                        self.__device.emit(uinput.KEY_UP, 0)
                    self.__tchbtn = False
                    return
                elif (B and self.__tchbtn == True):
                    for i in range(4):
                        self.__device.emit(uinput.KEY_DOWN, 1, syn = True)
                        self.__device.emit(uinput.KEY_DOWN, 0)
                    self.__tchbtn = False
                    return
                elif (outerCircle == False and self.__tchbtn == True):
                    self.__device.emit(uinput.BTN_LEFT, 1)
                    self.__tchbtn = False
                    # return is not feasable here
            else:
                self.__device.emit(uinput.BTN_LEFT, 0)

            if (homeButton == True and self.__volbtn == True):
                self.__device.emit(uinput.KEY_LEFTALT, 1)
                self.__device.emit(uinput.KEY_HOME, 1)
                self.__device.emit(uinput.KEY_HOME, 0)
                self.__device.emit(uinput.KEY_LEFTALT, 0)
                self.__volbtn = False
                return

            if (backButton == True and self.__volbtn == True):
                self.__device.emit(uinput.KEY_LEFTALT, 1)
                self.__device.emit(uinput.KEY_LEFT, 1)
                self.__device.emit(uinput.KEY_LEFT, 0)
                self.__device.emit(uinput.KEY_LEFTALT, 0)
                self.__volbtn = False
                return

            if (volumeDownButton == True and self.__volbtn == True):
                self.__device.emit(uinput.KEY_LEFTCTRL, 1, syn = False)
                self.__device.emit(uinput.KEY_KPMINUS, 1, syn = True)
                self.__device.emit(uinput.KEY_KPMINUS, 0, syn = False)
                self.__device.emit(uinput.KEY_LEFTCTRL, 0, syn = True)
                self.__volbtn = False
                return

            if (volumeUpButton == True and self.__volbtn == True):
                self.__volbtn = False
                self.__device.emit(uinput.KEY_LEFTCTRL, 1, syn = False)
                self.__device.emit(uinput.KEY_KPPLUS, 1, syn = True)
                self.__device.emit(uinput.KEY_KPPLUS, 0, syn = False)
                self.__device.emit(uinput.KEY_LEFTCTRL, 0, syn = True)
                self.__volbtn = False
                return

            if (NoButton == True):
                self.__volbtn = True
                self.__tchbtn = True
                self.__trig   = True
                self.__device.emit(uinput.BTN_LEFT, 0)
                self.__device.emit(uinput.KEY_PAGEUP, 0)
                self.__device.emit(uinput.KEY_PAGEDOWN, 0)
                self.__device.emit(uinput.KEY_UP, 0)
                self.__device.emit(uinput.KEY_DOWN, 0)
                self.__device.emit(uinput.KEY_LEFT, 0)
                self.__device.emit(uinput.KEY_RIGHT, 0)

            delta_X = delta_Y = 0
            delta_X = axisX - self.__axisX
            delta_Y = axisY - self.__axisY
            delta_X = round(delta_X * 1.2)
            delta_Y = round(delta_Y * 1.2)

            # No standalone button handling behind this point

            if (axisX == 0 and axisY == 0):
                self.__reset = True
                return

            if (self.__reset == True):
                self.__reset = False
                self.__axisX = axisX
                self.__axisY = axisY
                self.__altX = gyroX
                self.__altY = gyroY
                return

            self.movePointerREL(delta_X, delta_Y)

            self.__axisX = axisX
            self.__axisY = axisY
            self.__altX = gyroX
            self.__altY = gyroY
        else:
            print("got somethig else ", characteristic, " ",  len(value))

    def movePointerREL(self, dx, dy):
        incx = 0 if dx == 0 else round((0 - dx)/abs(dx))
        incy = 0 if dy == 0 else round((0 - dy)/abs(dy))

        while (dx != 0 or dy != 0):
            if (dx != 0):
                self.__device.emit(uinput.REL_X, -incx, syn = True)
                dx += incx
            if (dy != 0):
                self.__device.emit(uinput.REL_Y, -incy, syn = True)
                dy += incy

def defint():
    global device
    ##device.disconnect()
    sys.exit(0)

signal.signal(signal.SIGINT, lambda x,y: defint())

print("Samsung Gear VR Controller mapper running ...")
print("Press Ctrl+C to terminate")

device = AnyDevice(mac_address='2C:BA:BA:25:6A:A1', manager=manager)
device.connect()

manager.run()
