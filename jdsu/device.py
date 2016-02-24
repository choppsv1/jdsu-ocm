# -*- coding: utf-8 -*-#
#
# October 10 2015, Christian Hopps <chopps@gmail.com>
#
# Copyright (c) 2015-2016, Deutsche Telekom AG.
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from __future__ import absolute_import, division, unicode_literals, print_function, nested_scopes
import logging
import os
import pdb
import struct
from pkg_resources import Requirement, resource_filename
from sshutil.host import Host
from sshutil.conn import SSHCommandSession
from opticalutil.power import Power, Gain
from opticalutil.dwdm import frequency_to_wavelen
from jdsu.error import OCMError, get_error_result

logger = logging.getLogger(__name__)

from netconf import nsmap_update
nsmap_update({'j': "urn:TBD:params:xml:ns:yang:terastream:jdsu"})


"""
Message ID
Length
Command
Object ID
Instance
Parameter ID
Data Parameters                                             # up to 100/3000 words doc confused
Checksum
"""

"""
Message ID
Length
Error
Data Parameters up to 41004 words
Checksum
"""

MINRESPLEN = 2                                                # + 2 for frame
MAXRESPLEN = 41004
MINCMDLEN = 5                                                 # + 2 for frame
MAXCMDLEN = 100


"""
for 12.5GHz wide scan every 6.25Ghz, total 839 slices
1910000 -> 1962500 yields 5250.0 Ghz band

In [17]: 1962500 - 1910000
Out[17]: 52500

And there are 420 12.5GHz slices scanned twice except the final slice as
the device cannot measure the full 12.5GHz band.

In [18]: 52500 / 125
Out[18]: 420

In [19]: 52500 / 125 * 2
Out[19]: 840

"""

instance_map_4port = {
    0b1111: 0,                                                 # ALL
    0b0001: 1,                                                 # 1
    0b0010: 2,                                                 # 2
    0b0100: 3,                                                 # 3
    0b1000: 4,                                                 # 4
    0b0011: 5,                                                 # 1, 2
    0b0101: 6,                                                 # 1, 3
    0b1001: 7,                                                 # 1, 4
    0b0110: 8,                                                 # 2, 3
    0b1010: 9,                                                 # 2, 4
    0b1100: 10,                                                # 3, 4
    0b0111: 11,                                                # 1, 2, 3
    0b1011: 12,                                                # 1, 2, 4
    0b1101: 13,                                                # 1, 3, 4
    0b1110: 14                                                 # 2, 3, 4
}

inst_map = instance_map_4port

RESP_HDR = ">HHH"
RESP_0W  = RESP_HDR + "H"
RESP_1W  = RESP_0W + "H"
RESP_2W  = RESP_1W + "H"
RESP_3W  = RESP_2W + "H"
RESP_11W = RESP_HDR + "H" * 11
RESP_VAR = ""

APP_ONLY  = 0b01
SAFE_ONLY = 0b10
BOTH      = 0b11

PROFILE_ID_TAG = -1
PORT_NUM_TAG = -2
INST_MAP_TAG = -3

commands = {
    'START-SELF-TEST':    (1, 0, 1, 1, False, RESP_0W),
    'READ-FAIL-REG':      (2, 0, 1, 0, False, RESP_1W),
    'READ-FAIL-REG-TEMP': (2, 0, 2, 0, False, RESP_2W),
    'ACTIVATE':           (1, 1, 1, 1, False, RESP_0W),
    'DOWNLOAD-INIT':      (1, 2, 1, 1, False, RESP_0W),
    'DOWNLOAD':           (1, 3, 1, 1, True, RESP_0W),
    'GET-IDN-MSG':        (2, 4, 1, 0, False, RESP_VAR),
    'GET-MODULE-TEMP':    (2, 5, 1, 0, False, RESP_1W),
    'GET-APP-VERSION':   (2, 10, 1, 0, False, RESP_3W),
    'GET-SAFE-VERSION':  (2, 10, 2, 0, False, RESP_3W),
    'GET-MODULE-INFO':    (2, 11, 1, 0, False, RESP_VAR),
    'READ-PREV-CMD':      (2, 18, 4, 0, False, RESP_11W),
    'RESET':              (1, 79, 1, 1, False, RESP_0W),
    'CALIB-INIT':         (1, 14, 1, 1, False, RESP_0W),
    'CALIB-DOWNLOAD':     (1, 15, 1, 1, True, RESP_0W),
    'APPLY-CALIB':        (1, 16, 1, 1, False, RESP_0W),
    'GET-CALIB-VERSION':  (2, 17, 1, 0, False, RESP_3W),
    'SCAN':               (2, 75, INST_MAP_TAG, 0, True, RESP_VAR),
    'SET-PROFILE':        (1, 78, PROFILE_ID_TAG, 1, True, RESP_0W),
    'READ-PROFILE':       (2, 78, PROFILE_ID_TAG, 0, False, RESP_VAR),
    'FULL-SPECTRUM-SCAN': (2, 80, INST_MAP_TAG, 0, False, RESP_VAR),
    'FULL-12-SCAN':       (2, 82, INST_MAP_TAG, 0, False, RESP_VAR),
    'FULL-12-CH-SCAN':    (2, 84, INST_MAP_TAG, 0, True, RESP_VAR),
    'SET-FREQ':           (1, 85, PORT_NUM_TAG, 1, True, RESP_0W),
    'SCAN-DETECT-CHAN':   (2, 86, INST_MAP_TAG, 0, True, RESP_VAR),
    'SCAN-SPEC-DENSITY':  (2, 87, INST_MAP_TAG, 0, True, RESP_VAR),
    'SCAN-SPEC-DENSITY-CHAN': (2, 88, INST_MAP_TAG, 0, True, RESP_VAR),
}


def read_exact_len (jdsu, rlen):
    buf = b""
    blen = 0
    while blen < rlen:
        leftover = rlen - blen
        nbuf = jdsu.recv(leftover)
        nblen = len(nbuf)
        assert nblen <= leftover
        buf += nbuf
        blen += nblen
    return buf


def read_var_resp (jdsu):
    hdr = read_exact_len(jdsu, 6)
    if len(hdr) != 6:
        pdb.set_trace()
    msgid, mlen, result = struct.unpack('>HHH', hdr)
    assert mlen >= 2
    mlen -= 1
    rest = read_exact_len(jdsu, mlen * 2)
    if mlen > 1:
        data = rest[:-2]
    else:
        data = ""

    cksum = struct.unpack(">H", rest[-2:])[0]
    oursum = sum(unpack_data_words(rest[:-2])) + msgid + mlen + 1 + result
    oursum &= 0xFFFF
    if oursum != cksum:
        logger.error("BAD CKSUM: %s %s", str(unpack_data_words(hdr)), str(unpack_data_words(rest)))
        logger.error("BAD CKSUM: ours: %d theres: %d", oursum, cksum)

    return msgid, result, data


def instance_to_ports (bits):
    ports = []
    port = 0
    while bits:
        if bits & 0x1:
            ports.append(port)
        bits = (bits >> 1)
        port += 1
    return ports


def unpack_data_words (wordstring):
    wlen = len(wordstring)
    assert (wlen % 2) == 0
    wlen = wlen // 2
    return struct.unpack(">" + str(wlen) + "H", wordstring)


def unpack_data_string (wordstring):
    return wordstring.decode('ascii')


def unpack_signed_unsigned(data):
    nval = len(data) // 2
    spoints = struct.unpack(">" + str(nval) + "h", data)
    upoints = struct.unpack(">" + str(nval) + "H", data)
    return spoints, upoints


def unpack_signed(data):
    nval = len(data) // 2
    spoints = struct.unpack(">" + str(nval) + "h", data)
    return spoints


def unpack_unsigned(data):
    nval = len(data) // 2
    upoints = struct.unpack(">" + str(nval) + "H", data)
    return upoints


def get_next_msgid ():
    this_id = get_next_msgid.next
    get_next_msgid.next += 1
    return this_id
get_next_msgid.next = 1


def send_cmd(jdsu, cmdname, data=b"", instance=None, debug=False):
    cmdinfo = commands[cmdname]
    cmd = list(cmdinfo[0:4])
    if cmd[2] == INST_MAP_TAG:
        assert instance is not None
        cmd[2] = inst_map[instance]
    elif cmd[2] == PROFILE_ID_TAG:
        assert instance is not None
        cmd[2] = instance
    elif cmd[2] == PORT_NUM_TAG:
        assert instance is not None
        cmd[2] = instance

    if data:
        assert cmdinfo[4]
    else:
        assert not cmdinfo[4]
    dlen = len(data)
    assert (dlen % 2) == 0
    dwlen = dlen // 2
    clen = len(cmd) + dwlen + 1                             # +1 cksum
    rawcmd = [ get_next_msgid(), clen ] + list(cmd)
    cksum = sum(rawcmd)
    rawdata = struct.pack(">6H", *rawcmd)
    if data:
        cksum += sum(unpack_unsigned(data))
    rawdata += data + struct.pack(">H", cksum & 0xFFFF)
    rlen = len(rawdata) // 2
    assert clen == rlen - 2
    if debug:
        logger.debug("sending: %s", str(cmdname))
        logger.debug("sending: %s", str(unpack_unsigned(rawdata)))
    jdsu.send(rawdata)


class OCM (object):
    def __init__ (self, device, debug=False):
        self.device = device
        self.debug = debug
        assert not self.drain_serial_read_queue()

        idn = self.get_idn_data()
        if idn[2] != "SafeImage":
            # Reset the device on open.
            self.reset()

        self.activate()
        self.self_test()
        # print(self.get_module_info())
        # print(str(self.get_temp()))
        # print(self.get_safe_version())
        # print(self.get_app_version())

    def run_cmd_status(self, cmdname, data=b"", instance=None):
        send_cmd(self.device, cmdname, data, instance, debug=self.debug)
        respfmt = commands[cmdname][5]
        if not respfmt:
            unused, error, data = read_var_resp(self.device)
        else:
            resplen = (len(respfmt) - 1) * 2
            rdata = read_exact_len(self.device, resplen)
            unused_msgid, unused_mlen, error = struct.unpack('>HHH', rdata[:6])
            data = rdata[6:-2]
            cksum = rdata[-2:]
            # XXX check cksum
            # XXX verify len
        if error:
            logging.debug("Command %s failed with result: %s", cmdname, get_error_result(error))

        return error, data

    def run_cmd(self, cmdname, data=b"", instance=None):
        error, data = self.run_cmd_status(cmdname, data, instance)
        if error:
            raise OCMError(error)
        return data

    def drain_serial_read_queue (self):
        while self.device.recv_ready():
            extra = self.device.recv()
            if extra:
                print("Got {} extra leftover bytes".format(len(extra)))

    def reset (self):
        self.run_cmd("RESET")
        assert not self.drain_serial_read_queue()

    def activate (self):
        self.run_cmd("ACTIVATE")

    def get_idn_string (self):
        # IDN is made of of ASCII characters in 16 bit values.
        wordstring = self.run_cmd("GET-IDN-MSG")
        wlen = len(wordstring)
        assert (wlen % 2) == 0
        wlen = wlen // 2
        data = "".join([ chr(x) for x in struct.unpack(">" + str(wlen) + "H", wordstring) ])
        return data.decode('ascii')

    def get_idn_data (self):
        return self.get_idn_string().split(",")

    def get_oper_mode (self):
        idn = self.get_idn_data()
        oper_mode = "safe-mode" if idn[2] == "SafeImage" else "application-mode"
        return oper_mode

    def self_test (self):
        self.run_cmd("START-SELF-TEST")

    def get_safe_version (self):
        return "{}.{}.{}".format(*unpack_data_words(self.run_cmd("GET-SAFE-VERSION")))

    def get_app_version (self):
        return "{}.{}.{}".format(*unpack_data_words(self.run_cmd("GET-APP-VERSION")))

    def get_fail_reg (self):
        return unpack_data_words(self.run_cmd("READ-FAIL-REG"))[0]

    def get_fail_reg_temp (self):
        data = unpack_data_words(self.run_cmd("READ-FAIL-REG-TEMP"))
        return data[0], data[1] / 10

    def get_temp (self):
        return unpack_data_words(self.run_cmd("GET-MODULE-TEMP"))[0] / 10

    def get_temp_int (self):
        return unpack_data_words(self.run_cmd("GET-MODULE-TEMP"))[0]

    def get_module_info (self):
        return unpack_data_string(self.run_cmd("GET-MODULE-INFO"))

    def get_channel_profile (self, profile_id):
        data = self.run_cmd("READ-PROFILE", instance=profile_id)
        nchan = struct.unpack(">H", data[:2])[0]
        data = data[2:]
        if len(data) != nchan * 4:
            raise ValueError("Frequencies returned {} different from expected {}".format(len(data) // 2, nchan * 2))
        freqlist = [ x + 1900000 for x in unpack_unsigned(data) ]
        if len(freqlist) % 1 != 0:
            raise ValueError("Channel frequencies not paired, total frequency count {}".format(len(freqlist)))
        freqlist = zip(freqlist[::2], freqlist[1::2])
        return freqlist

    def get_full_scan (self, instance=0b1111):
        data = self.run_cmd("FULL-SPECTRUM-SCAN", instance=instance)

        nports = struct.unpack(">H", data[0:2])[0]
        data = data[2:]
        if self.debug:
            logger.debug("FSCAN: Port Count: %d", nports)

        result = []
        for port in instance_to_ports(instance):
            npoints = struct.unpack(">H", data[:2])[0]
            data = data[2:]

            spoints, upoints = unpack_signed_unsigned(data[:4 * npoints])
            data = data[4 * npoints:]

            if self.debug:
                logger.debug("FSCAN PORT %s points %d", port, npoints)

            rpoints = []
            for freq, power in zip(upoints[::2], spoints[1::2]):
                power = Power(power / 100) + Gain(20)       # Tap is 1% so add 20dB
                freq = 1900000 + freq
                rpoints.append((freq, power))

            lrpoints = len(rpoints)
            if npoints != lrpoints:
                raise ValueError("Returned points {} different from expected {}".format(lrpoints, npoints))

            result.append((port, rpoints))

        # Want better error here.
        if data:
            raise ValueError("Extra data form OCM of len: {}".format(len(data)))

        return result

    def get_full_125_scan (self, instance=0b1111):
        data = self.run_cmd("FULL-12-SCAN", instance=instance)

        nports = struct.unpack(">H", data[0:2])[0]
        data = data[2:]
        if self.debug:
            logger.debug("FSCAN125x625: Port Count: %s", str(nports))

        result = []
        for port in instance_to_ports(instance):
            npoints = struct.unpack(">H", data[:2])[0]
            data = data[2:]
            if npoints != 839:
                raise ValueError("Too man points %d (not 839) in 12.5x6.25 scan", npoints)

            spoints = struct.unpack(">" + str(npoints) + "h", data[:2 * npoints])
            data = data[2 * npoints:]

            if self.debug:
                logger.debug("FSCAN125x625 PORT %d points %d", port, npoints)

            rpoints = []
            # Start of scan range
            freq = 191000
            for power in spoints:
                rpoints.append((freq, Power(power / 100) + Gain(20)))
                freq += 6.25

            lrpoints = len(rpoints)
            if npoints != lrpoints:
                raise ValueError("Returned points {} different from expected {}".format(lrpoints, npoints))

            result.append((port, rpoints))

        if data:
            raise ValueError("Extra data form OCM of len: {}".format(len(data)))

        return result

    def dump_channel_scan (self):
        data = struct.pack(">HHHH", 2, 2, 2, 2)
        data = self.run_cmd("FULL-12-CH-SCAN", data=data, instance=0b1111)

        nports = struct.unpack(">H", data[0:2])[0]
        data = data[2:]
        print("FSCAN: Port Count: {}".format(nports))

        port = 1
        while data:
            nchan = struct.unpack(">H", data[:2])[0]
            data = data[2:]
            print("FSCAN PORT {} Channel count {}".format(port, nchan))

            chandata = data[:nchan * 3 * 2]
            data = data[nchan * 3 * 2:]
            spoints = struct.unpack(">" + str(nchan * 3) + "h", chandata)
            upoints = struct.unpack(">" + str(nchan * 3) + "H", chandata)
            with open("fpcs-{}.csv".format(port), "w") as f:
                for freq, power, present in zip(upoints[::3], spoints[1::3], upoints[2::3]):
                    power = Power(power / 100) + Gain(20)
                    freq = (1900000 + freq) / 10
                    if True or power > Power(-25):
                        print("FSCAN PORT {} CHFRQ: {}\tPWR: {}\tPRES: {}".format(port,
                                                                                  freq,
                                                                                  power,
                                                                                  present))
                    f.write("{}\t{}\n".format(freq, power))
            npoints = struct.unpack(">H", data[:2])[0]
            data = data[2:]

            pdata = data[:npoints * 2]
            data = data[2 * npoints:]
            spoints = struct.unpack(">" + str(npoints) + "h", pdata)

            # print("FSCAN PORT {} points {}".format(port, npoints))
            # for idx, power in enumerate(spoints):
            #     power = Power(power / 100) + Gain(20)
            #     if power > Power(-30):
            #         print("FSCAN PORT {}: SLICE IDX: {}\tPWR: {}".format(port,
            #                                                              idx,
            #                                                              power))
            port += 1

    def dump_spectral_density (self):
        data = struct.pack(">HHHH", 2, 2, 2, 2)
        data = self.run_cmd("SCAN-SPEC-DENSITY", data=data, instance=0b1111)

        nports = struct.unpack(">H", data[0:2])[0]
        data = data[2:]
        print("FSCAN: Port Count: {}".format(nports))

        port = 1
        while data:
            npoints = struct.unpack(">H", data[:2])[0]
            data = data[2:]
            spoints = struct.unpack(">" + str(npoints * 3) + "h", data[:6 * npoints])
            upoints = struct.unpack(">" + str(npoints * 3) + "H", data[:6 * npoints])
            data = data[6 * npoints:]
            print("SPDENSE PORT {} points {}".format(port, npoints))
            with open("sd-{}.csv".format(port), "w") as f:
                for freq, avgpower, maxpower in zip(upoints[::3], spoints[1::3], spoints[2::3]):
                    avgpower = Power(avgpower / 100) + Gain(20)
                    maxpower = Power(maxpower / 100) + Gain(20)
                    freq = (1900000 + freq) / 10
                    print("SPDENSE PORT {}: FRQ: {}\tWVL: "
                          "{}\t Avg Pwr: {}\tMax Pwr: {}".format(port,
                                                                 freq,
                                                                 frequency_to_wavelen(freq),
                                                                 avgpower,
                                                                 maxpower))
                    f.write("{}\t{}\t{}\n".format(freq, avgpower, maxpower))
            port += 1

    def read_channel_profile (self):
        # XXX errors?
        for profile_id in range(1, 16):
            pass

    def write_channel_profile (self):
        freqlist = []
        nchan = 0
        for freq in range(11000, 61000, 1000):
            freqlist.append(freq - 125)
            freqlist.append(freq + 125)
            nchan += 1

        data = struct.pack(">H", nchan)
        data += struct.pack(">" + str(nchan * 2) + "H", *freqlist)
        self.run_cmd("SET-PROFILE", data=data, instance=2)


class LocalOCM (OCM):
    def __init__ (self, devname, debug=False):
        import serial
        self.serial = serial.Serial(port=devname,
                                    timeout=0,
                                    baudrate=115200,
                                    parity=serial.PARITY_NONE,
                                    stopbits=serial.STOPBITS_ONE,
                                    xonxoff=False,
                                    rtscts=False,
                                    bytesize=serial.EIGHTBITS)
        # if debug:
        #     sys.stderr.write("sercat: Opening serial\n")
        # #syslog.syslog("sercat: Opening serial\n")
        # ### serial.open()
        # serial.nonblocking()
        # if debug:
        #     sys.stderr.write("sercat: Opened serial\n")
        # #syslog.syslog("sercat: Opened serial\n")
        super(LocalOCM, self).__init__(self.serial, debug=debug)


class RemoteOCM (OCM):
    def __init__ (self, jdsu_host, devname, username=None, password=None, debug=False):
        self.host = jdsu_host

        # Copy latest sercat
        sercat_path = resource_filename(Requirement.parse("jdsu"), "jdsu/sercat.py")
        assert os.path.exists(sercat_path)
        rhost = Host(jdsu_host, username=username, password=password, debug=debug)
        rhost.copy_to(sercat_path, "./sercat.py")

        # Open the connection to the serial port.
        self.session = SSHCommandSession(jdsu_host,
                                         22,
                                         "/usr/bin/python -u sercat.py " + devname,
                                         username=username,
                                         password=password)
        self.log_sercat_stderr()                            # Start the stderr logger.

        super(RemoteOCM, self).__init__(self.session, debug=debug)

    def log_sercat_stderr (self):
        import threading

        def threadmain ():
            data = ""
            while True:
                data += self.session.recv_stderr()
                try:
                    while True:
                        idx = data.index("\n")
                        logger.warn("SERCAT (%s) STDERR: %s", self.host, data[:idx])
                        data = data[idx + 1:]
                except ValueError:
                    break

        logger_thread = threading.Thread(target=threadmain)
        logger_thread.daemon = True
        logger_thread.start()


__author__ = 'Christian Hopps'
__date__ = 'October 10 2015'
__version__ = '1.0'
__docformat__ = "restructuredtext en"
