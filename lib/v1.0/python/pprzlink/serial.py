from __future__ import absolute_import, division, print_function

import threading
import serial

from .message import PprzMessage
from .pprz_transport import PprzTransport


class SerialMessagesInterface(threading.Thread):
    def __init__(self, callback, cb_disconnect=None, verbose=False, device='/dev/ttyUSB0', baudrate=115200,
                 msg_class='telemetry'):
        threading.Thread.__init__(self)
        self.callback = callback
        self.cb_disconnect = cb_disconnect
        self.verbose = verbose
        self.device = device
        self.msg_class = msg_class
        self.running = True
        try:
            self.ser = serial.Serial(self.device, baudrate, timeout=1.0)
        except serial.SerialException:
            print("Error: unable to open serial port '%s'" % device)
            exit(0)
        self.trans = PprzTransport(msg_class)

    def stop(self):
        if self.verbose:
            print("End thread and close serial link")
        self.running = False
        try:
            self.ser.close()
        except:
            pass

    def shutdown(self):
        self.stop()

    def disconnect(self):
        if self.cb_disconnect != None:
            self.cb_disconnect()
        self.stop()

    def __del__(self):
        try:
            self.stop()
        except:
            pass

    def send(self, msg, sender_id):
        """ Send a message over a serial link"""
        if isinstance(msg, PprzMessage):
            data = self.trans.pack_pprz_msg(sender_id, msg)
            self.ser.write(data)
            self.ser.flush()

    def run(self):
        """Thread running function"""
        try:
            while self.running:
                # Parse incoming data
                c = self.ser.read(1)
                if len(c) == 1:
                    if self.trans.parse_byte(c):
                        (sender_id, msg) = self.trans.unpack()
                        if self.verbose:
                            print("New incoming message '%s' from %i" % (msg.name, sender_id))
                        # Callback function on new message 
                        self.callback(sender_id, msg)

        except StopIteration:
            pass
        except serial.SerialException:
            self.disconnect()


def test():
    import time
    import argparse
    from . import messages_xml_map

    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", help="path to messages.xml file")
    parser.add_argument("-c", "--class", help="message class", dest='msg_class', default='telemetry')
    parser.add_argument("-d", "--device", help="device name", dest='dev', default='/dev/ttyUSB0')
    parser.add_argument("-b", "--baudrate", help="baudrate", dest='baud', default=115200, type=int)
    args = parser.parse_args()
    messages_xml_map.parse_messages(args.file)
    serial_interface = SerialMessagesInterface(lambda s, m: print("new message from %i: %s" % (s, m)), device=args.dev,
                                               baudrate=args.baud, msg_class=args.msg_class, verbose=True)

    print("Starting serial interface on %s at %i baud" % (args.dev, args.baud))
    try:
        serial_interface.start()

        # give the thread some time to properly start
        time.sleep(0.1)

        # send some datalink messages to aicraft for test
        ac_id = 42
        print("sending ping")
        ping = PprzMessage('datalink', 'PING')
        serial_interface.send(ping, 0)

        get_setting = PprzMessage('datalink', 'GET_SETTING')
        get_setting['index'] = 0
        get_setting['ac_id'] = ac_id
        serial_interface.send(get_setting, 0)

        # change setting with index 0 (usually the telemetry mode)
        set_setting = PprzMessage('datalink', 'SETTING')
        set_setting['index'] = 0
        set_setting['ac_id'] = ac_id
        set_setting['value'] = 1
        serial_interface.send(set_setting, 0)

        # block = PprzMessage('datalink', 'BLOCK')
        # block['block_id'] = 3
        # block['ac_id'] = ac_id
        # serial_interface.send(block, 0)

        while serial_interface.isAlive():
            serial_interface.join(1)
    except (KeyboardInterrupt, SystemExit):
        print('Shutting down...')
        serial_interface.stop()
        exit()


if __name__ == '__main__':
    test()
