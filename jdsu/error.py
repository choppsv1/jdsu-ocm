# -*- coding: utf-8 -*-#
#
# October 11 2015, Christian Hopps <chopps@gmail.com>
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

#--------------------
# Error Result Codes
#--------------------

ENOERR = 0
EBADCMD = 1
EVALRANGE = 2
EFAILED = 3
EPERM = 4
EBADCALIB = 5
EFIRMSIZE = 6
EMODTYPE = 7
EFIRMCKSUM = 8
EFRAMECKSUM = 9
EPROTOCOL = 10
ESUCCESSHARDFAIL = 11
EFAILHARDFAIL = 12
error_string = {
    ENOERR: "ENOERR",
    EBADCMD: "EBADCMD",
    EVALRANGE: "EVALRANGE",
    EFAILED: "EFAILED",
    EPERM: "EPERM",
    EBADCALIB: "EBADCALIB",
    EFIRMSIZE: "EFIRMSIZE",
    EMODTYPE: "EMODTYPE",
    EFIRMCKSUM: "EFIRMCKSUM",
    EFRAMECKSUM: "EFRAMECKSUM",
    EPROTOCOL: "EPROTOCOL",
    ESUCCESSHARDFAIL: "ESUCCESSHARDFAIL",
    EFAILHARDFAIL: "EFAILHARDFAIL",
}

#--------------------
# HW Failure Bitmask
#--------------------

EHW_TEMP = 0x2
EHW_CALIB = 0x4
EHW_APP_CORRUPT = 0x8
EHW_SCAN = 0x10
EHW_OTHER = 0x10
EHW_FLASH_FAIL = 0x80


def get_error_result (result):
    if result not in error_string:
        return "Unknown error: " + str(result)
    return error_string[result]


class OCMError (Exception):
    def __init__ (self, error):
        self.error = error
        self.errstr = get_error_result(error)
        super (OCMError, self).__init__(self.errstr)


__author__ = 'Christian Hopps'
__date__ = 'October 11 2015'
__version__ = '1.0'
__docformat__ = "restructuredtext en"
