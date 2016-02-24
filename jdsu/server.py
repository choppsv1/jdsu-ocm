# -*- coding: utf-8 -*-#
#
# October 12 2015, Christian Hopps <chopps@gmail.com>
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
import threading
from pkg_resources import Requirement, resource_filename

import netconf.util as ncutil
import netconf.error as ncerror
import netconf.server as server
from netconf import nsmap_update, NSMAP, qmap

import jdsu.error as error

nsmap_update({'j': "urn:TBD:params:xml:ns:yang:terastream:jdsu"})


logger = logging.getLogger(__name__)


class NetconfServer (object):
    NCFILTER = qmap("nc") + "filter"

    def __init__ (self, device, host_key, ssh_port=830, username=None, password=None, debug=False):
        #-----------------
        # Open the device
        #-----------------
        self.debug = debug

        datapath = resource_filename(Requirement.parse("jdsu"), "data")
        host_key_path = os.path.expanduser(host_key)
        assert os.path.exists(host_key_path)

        idn = device.get_idn_data()

        # XXX Is this where we get the port count?
        assert idn[4] == "cal04"
        self.nports = 4

        self.device = device
        self.device_lock = threading.Lock()

        #-----------------------
        # Start the server.
        #-----------------------

        self.controller = server.SSHUserPassController(username=username,
                                                       password=password)

        self.server = server.NetconfSSHServer(server_ctl=self.controller,
                                              port=ssh_port,
                                              host_key=host_key_path,
                                              server_methods=self,
                                              debug=debug)
        logger.info("Listening on port %d", self.server.port)

    def join (self):
        "Wait on server to terminate"
        self.server.join()

    def nc_append_capabilities (self, caps):
        ncutil.subelm(caps, "capability").text = NSMAP['j']

    def _run_device_method (self, rpc, method, *args, **kwargs):
        try:
            with self.device_lock:
                return method(*args, **kwargs)
        except error.OCMError as err:
            raise ncerror.RPCServerError(rpc,
                                         ncerror.RPCERR_TYPE_APPLICATION,
                                         ncerror.RPCERR_TAG_OPERATION_FAILED,
                                         message=str(err))
        except Exception as ex:
            raise ncerror.RPCServerError(rpc,
                                         ncerror.RPCERR_TYPE_APPLICATION,
                                         ncerror.RPCERR_TAG_OPERATION_FAILED,
                                         app_tag="unexpected-error",
                                         message=str(ex))

    def rpc_activate (self, unused, rpc, *params):
        # Input values
        if params:
            raise ncerror.RPCSvrErrBadMsg(rpc)

        self._run_device_method(rpc, self.device.activate)
        return ncutil.elm("ok")

    def rpc_self_test (self, unused, rpc, *params):
        # Input values
        if params:
            raise ncerror.RPCSvrErrBadMsg(rpc)

        self._run_device_method(rpc, self.device.self_test)
        return ncutil.elm("ok")

    def rpc_reset (self, unused, rpc, *params):
        # Input values
        if params:
            raise ncerror.RPCSvrErrBadMsg(rpc)

        self._run_device_method(rpc, self.device.reset)
        return ncutil.elm("ok")

    def rpc_full_scan (self, unused_session, rpc, *params):
        # No input values yet
        if params:
            raise ncerror.RPCSvrErrBadMsg(rpc)

        rv = self._run_device_method(rpc, self.device.get_full_scan)

        result = ncutil.elm("data")
        # result = []
        for port, points in rv:
            portelm = ncutil.elm("j:port")
            result.append(portelm)
            portelm.append(ncutil.leaf_elm("j:port-index", port))
            for freq, power in points:
                ptelm = ncutil.subelm(portelm, "j:point")
                ptelm.append(ncutil.leaf_elm("j:frequency", freq))
                ptelm.append(ncutil.leaf_elm("j:power", "{:.2f}".format(power.dBm)))
        return result

    def rpc_full_125_scan (self, unused_session, rpc, *params):
        # No input values yet
        if params:
            raise ncerror.RPCSvrErrBadMsg(rpc)

        rv = self._run_device_method(rpc, self.device.get_full_125_scan)

        result = ncutil.elm("data")
        for port, points in rv:
            # portelm = etree.Element(ncutil.qname("j:port"), nsmap={ 'j': NSMAP['j'] })
            portelm = ncutil.elm("j:port")
            result.append(portelm)
            portelm.append(ncutil.leaf_elm("j:port-index", port))
            for freq, power in points:
                ptelm = ncutil.subelm(portelm, "j:point")
                ptelm.append(ncutil.leaf_elm("j:frequency", freq))
                ptelm.append(ncutil.leaf_elm("j:power", "{:.2f}".format(power.dBm)))
        return result

    def rpc_get_config (self, unused_session, rpc, source_elm, unused_filter_elm):
        assert source_elm is not None
        if source_elm.find("nc:running", namespaces=NSMAP) is None:
            raise ncerror.RPCSvrMissingElement(rpc, ncutil.elm("nc:running"))

        config = ncutil.elm("data")
        for idx in range(1, 17):
            profile_elm = ncutil.elm("j:channel-profile")
            config.append(profile_elm)
            profile_elm.append(ncutil.leaf_elm("j:profile-index", idx))

            channels = self.device.get_channel_profile(idx)
            for freqs, freqe in channels:
                channel_elm = ncutil.subelm(profile_elm, "j:channel")
                range_elm = ncutil.subelm(channel_elm, "j:range")
                range_elm.append(ncutil.leaf_elm("j:frequency-start", freqs))
                range_elm.append(ncutil.leaf_elm("j:frequency-end", freqe))

        return config

    def rpc_get (self, unused_session, unused_rpc, filter_elm):
        data = ncutil.elm("data")

        get_data_methods = {
            ncutil.qname("j:oper-mode").text: self.device.get_oper_mode,
            ncutil.qname("j:ident-data").text: self.device.get_idn_string,
            ncutil.qname("j:device-info").text: self.device.get_module_info,
            ncutil.qname("j:safe-version").text: self.device.get_safe_version,
            ncutil.qname("j:application-version").text: self.device.get_app_version,
            ncutil.qname("j:temp").text: self.device.get_temp_int,
        }

        infonode = ncutil.elm("j:info")
        # infonode = etree.Element(ncutil.qname("j:info"), nsmap={ 'j': NSMAP['j'] })

        # Get filter children
        children = []
        if filter_elm is not None:
            children = filter_elm.getchildren() if filter_elm is not None else []

        def get_all_values ():
            leaf_elms = []
            for key, valuef in get_data_methods.items():
                leaf_elms.append(ncutil.leaf_elm(key, valuef()))
            return leaf_elms

        # No filter children return info only
        if not children:
            ncutil.filter_leaf_values(None, infonode, get_all_values(), data)
            return data

        # Look for info filter.
        finfo = filter_elm.find("info") or filter_elm.find("j:info", namespaces=NSMAP)
        if finfo is not None:
            children = finfo.getchildren()
            if not children:
                leaf_elms = get_all_values()
            else:
                leaf_elms = []
                for felm in children:
                    tag = felm.tag
                    if tag in get_data_methods:
                        leaf_elms.append(ncutil.leaf_elm(tag, get_data_methods[tag]()))
            rv = ncutil.filter_leaf_values(finfo, infonode, leaf_elms, data)
            # Some selector doesn't match return empty.
            if rv is False:
                logger.error("XXX returning False")
                return data

        return data


__author__ = 'Christian Hopps'
__date__ = 'October 12 2015'
__version__ = '1.0'
__docformat__ = "restructuredtext en"