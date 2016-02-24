# -*- coding: utf-8 -*-#
#
# October 3 2015, Christian Hopps <chopps@gmail.com>
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
import argparse
import logging
import os
import sys
from paramiko import RSAKey
import jdsuocm.device as device
import jdsuocm.server as server


def main (*margs):
    parser = argparse.ArgumentParser("JDSU-OCM Netconf Server")

    parser.add_argument("--server-port", type=int, default=830, help="Port for netconf to listen on")
    parser.add_argument("--server-username", default="admin", help="Netconf user")
    parser.add_argument("--server-password", default="admin", help="Netconf password")
    parser.add_argument("--server-host-key", help="Server SSH Host Key")
    parser.add_argument("--device-host", help="The remote JDSU host to run sercat on otherwise local")
    parser.add_argument("--device-name", default="/dev/ttyUSB0", help="The serial port device")
    parser.add_argument("--device-username", help="The username to login with")
    parser.add_argument("--device-password", help="The password to login with")
    parser.add_argument("--device-key", help="SSH Private key to use")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args(*margs)

    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    elif args.verbose:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)
    logger = logging.getLogger(__name__)

    # Mutually exclusive
    if args.device_password and args.device_key:
        logger.critical("Can't specify both --device-key and --device-password")
        sys.exit(1)

    if not args.server_host_key or not os.path.exists(os.path.expanduser(args.server_host_key)):
        logger.critical("Server host ssh key required.")
        sys.exit(1)

    if not args.device_host:
        jdsu = device.LocalOCM(args.device_name, debug=args.debug)
    else:
        if args.device_key:
            password = RSAKey.from_private_key_file(args.device_key)
        else:
            password = args.device_password
        jdsu = device.RemoteOCM(args.device_host,
                                args.device_name,
                                username=args.device_username,
                                password=password,
                                debug=args.debug)

    ncserver = server.NetconfServer(jdsu,
                                    args.server_host_key,
                                    ssh_port=args.server_port,
                                    username=args.server_username,
                                    password=args.server_password,
                                    debug=args.debug)
    ncserver.join()

if __name__ == "__main__":
    main()


# print(etree.tounicode(jdsu.get_full_scan(), pretty_print=True))
# jdsu.dump_full_125_scan()
# jdsu.dump_channel_scan()
# jdsu.dump_spectral_density()
# jdsu.write_channel_profile()
# jdsu.read_channel_profile()

# XXX add to delete?
# assert not drain_serial_read_queue(jdsu)
