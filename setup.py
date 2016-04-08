# -*- coding: utf-8 -*-#
#
# Copyright (c) 2015-2016, Deutsche Telekom AG.
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
import os
from setuptools import setup

required = [
    "netconf",
    "opticalutil",
    "pyserial",
    "sshutil"
]


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

setup (name='jdsuocm',
       version='0.1.1',
       description='JDSU OCM',
       long_description=read("README.rst"),
       author='Christian E. Hopps',
       author_email='chopps@gmail.com',
       license='Apache License, Version 2.0',
       install_requires=required,
       url='https://github.com/choppsv1/jdsu-ocm',
       entry_points={ "console_scripts": [ "jdsu-scan = jdsuocm.scan:main",
                                           "jdsu-server = jdsuocm.main:main" ]},
       packages=['jdsuocm'])
