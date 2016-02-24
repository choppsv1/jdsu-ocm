#!/usr/bin/python -u
# -*- coding: utf-8 -*-#
#
# Copyright (c) 2015 by Christian E. Hopps
# All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
#; distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
from __future__ import absolute_import, division, print_function, nested_scopes
import select
import serial
import sys
import syslog


def main (devname, debug=False):
    serdev = serial.Serial(port=devname,
                           timeout=0,
                           baudrate=115200,
                           parity=serial.PARITY_NONE,
                           stopbits=serial.STOPBITS_ONE,
                           xonxoff=False,
                           rtscts=False,
                           bytesize=serial.EIGHTBITS)
    if debug:
        sys.stderr.write("sercat: Opening serial\n")
    #syslog.syslog("sercat: Opening serdev\n")
    ### serial.open()
    serdev.nonblocking()
    if debug:
        sys.stderr.write("sercat: Opened serial\n")
    #syslog.syslog("sercat: Opened serial\n")

    # try:
    #    import fcntl
    #    fcntl.fcntl(sys.stdin.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)
    # except Exception as error:
    #    syslog.syslog("sercat: error with fcntl: %s\n", str(error))

    try:
        while True:
            syslog.syslog("sercat: selecting\n")
            readfds, unused, unused = select.select([ sys.stdin, serdev ], [], [])
            if sys.stdin in readfds:
                if debug:
                    sys.stderr.write("sercat: Stdin read ready\n")
                # syslog.syslog("sercat: Stdin read ready\n")
                # inbuf = sys.stdin.read(1)
                inbuf = sys.stdin.read(1)
                if not inbuf:
                    # syslog.syslog("sercat: Exiting cleanly due to EOF on stdin")
                    if debug:
                        sys.stderr.write("Exiting due to EOF on stdin\n")
                    sys.exit(0)
                if debug:
                    sys.stderr.write("sercat: Stdin read {} bytes\n".format(len(inbuf)))
                # syslog.syslog("sercat: Stdin read {} bytes\n".format(len(inbuf)))
                outcount = serdev.write(inbuf)
                if debug:
                    sys.stderr.write("sercat: Serial wrote {} bytes\n".format(outcount))
                # syslog.syslog("sercat: Serial wrote {} bytes\n".format(outcount))
                assert outcount == len(inbuf)
            if serdev in readfds:
                if debug:
                    sys.stderr.write("sercat: Serial read ready\n")
                # syslog.syslog("sercat: Serial read ready\n")
                n = serdev.inWaiting()
                if not n:
                    # syslog.syslog("sercat: Error read ready on serial but no chars!")
                    if debug:
                        sys.stderr.write("Error read ready on serial but no chars!\n")
                    sys.exit(1)
                else:
                    if debug:
                        sys.stderr.write("sercat: Serial reading {} bytes\n".format(n))
                    # syslog.syslog("sercat: Serial reading {} bytes\n".format(n))
                    outbuf = serdev.read(n)
                    if debug:
                        sys.stderr.write("sercat: Serial read {} bytes\n".format(len(outbuf)))
                    # syslog.syslog("sercat: Serial read {} bytes\n".format(len(outbuf)))
                    sys.stdout.write(outbuf)
                    if debug:
                        sys.stderr.write("sercat: Stdout wrote {} bytes\n".format(len(outbuf)))
                    # syslog.syslog("sercat: Stdout wrote {} bytes\n".format(len(outbuf)))
    except Exception as error:
        syslog.syslog("sercat: error in try: %s\n", str(error))


if __name__ == "__main__":
    # Could process all the serial settings here..
    main(sys.argv[1])
