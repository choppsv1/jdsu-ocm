# -*- coding: utf-8 -*-#
#
# October 16 2015, Christian Hopps <chopps@gmail.com>
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
import io
import sys
from netconf import client
from netconf import NSMAP, nsmap_update


nsmap_update({'j': "urn:TBD:params:xml:ns:yang:terastream:jdsu"})


def main (*margs):
    parser = argparse.ArgumentParser("JDSU-Scan to CSV")

    parser.add_argument("--full-125", action="store_true", help="Do 12.5GHz scan otherwise normal full.")
    parser.add_argument("--host", default="localhost", help="The host to connect to (default: localhost)")
    parser.add_argument("--port", type=int, default=9931, help="The port to connect to (default: 9931)")
    parser.add_argument("--scan-port", type=int, default=None, help="The port to scan")
    parser.add_argument("--output-prefix", default="jdsu-scan",
                        help="The Prefix of the csv file to output per port")
    parser.add_argument("--username", default="admin", help="The username to login with")
    parser.add_argument("--password", default="admin", help="The password to login with")
    parser.add_argument("-v", "--verbose", action="store_true", help="The password to login with")
    args = parser.parse_args(*margs)

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    session = client.NetconfSSHSession(args.host,
                                       username=args.username,
                                       password=args.password,
                                       port=args.port,
                                       debug=args.verbose)

    try:
        if args.full_125:
            unused, reply, unused = session.send_rpc("""<full-125-scan/>""")
        else:
            unused, reply, unused = session.send_rpc("""<full-scan/>""")
    except Exception as ex:
        logging.error("Scan failed: %s", str(ex))
        sys.exit(1)

    if reply is None:
        logging.error("Scan failed")
    else:
        if args.scan_port is not None:
            start, end = args.scan_port, args.scan_port + 1
        else:
            start, end = 0, 4

        for port in range(start, end):
            xpath_prefix = "*/j:port[j:port-index='{}']/j:point/".format(port)

            freqlist = reply.findall(xpath_prefix + "j:frequency", namespaces=NSMAP)
            freqlist = [ x.text for x in freqlist if x is not None and x.text]

            powerlist = reply.findall(xpath_prefix + "j:power", namespaces=NSMAP)
            powerlist = [ x.text for x in powerlist if x is not None and x.text]

            with open(args.output_prefix + "-" + str(port) + ".csv", "w") as output:
                for x, y in zip(freqlist, powerlist):
                    output.write("{}\t{}\t{}\n".format(port, x, y))


if __name__ == "__main__":
    main()
