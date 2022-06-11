# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

import copy
import json
import os
from collections import OrderedDict

import yaml


# minimalistic raml loader. Support !include tags, and mapping as OrderedDict
class RamlLoader(yaml.SafeLoader):
    pass


def construct_include(loader, node):
    path = os.path.join(os.path.dirname(loader.stream.name), node.value)
    with open(path, encoding='utf-8') as f:
        return yaml.load(f, Loader=RamlLoader)


def construct_mapping(loader, node):
    loader.flatten_mapping(node)
    return OrderedDict(loader.construct_pairs(node))


RamlLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    construct_mapping)
RamlLoader.add_constructor('!include', construct_include)


class RamlSpec:

    """
    This class loads the raml specification, and expose useful
    aspects of the spec

    Main usage for now is for the doc, but it can be extended to make sure
    raml spec matches other spec implemented in the tests
    """

    def __init__(self):
        fn = os.path.join(os.path.dirname(__file__),
                          os.pardir, 'spec', 'api.raml')
        with open(fn, encoding='utf-8') as f:
            self.api = yaml.load(f, Loader=RamlLoader)

        with open(fn, encoding='utf-8') as f:
            self.rawraml = f.read()

        endpoints = {}
        self.endpoints_by_type = {}
        self.rawendpoints = {}
        self.endpoints = self.parse_endpoints(endpoints, "", self.api)
        self.types = self.parse_types()

    def parse_endpoints(self, endpoints, base, api, uriParameters=None):
        if uriParameters is None:
            uriParameters = OrderedDict()

        for k, v in api.items():
            if k.startswith("/"):
                ep = base + k
                p = copy.deepcopy(uriParameters)
                if v is not None:
                    p.update(v.get("uriParameters", {}))
                    v["uriParameters"] = p
                    endpoints[ep] = v
                self.parse_endpoints(endpoints, ep, v, p)
            elif k in ['get', 'post']:
                if 'is' not in v:
                    continue

                for _is in v['is']:
                    if not isinstance(_is, dict):
                        raise Exception(f'Unexpected "is" target {type(_is)}: {_is}')

                    if 'bbget' in _is:
                        try:
                            v['eptype'] = _is['bbget']['bbtype']
                        except TypeError as e:
                            raise Exception(f"Unexpected 'is' target {_is['bbget']}") from e

                        self.endpoints_by_type.setdefault(v['eptype'], {})
                        self.endpoints_by_type[v['eptype']][base] = api

                    if 'bbgetraw' in _is:
                        self.rawendpoints.setdefault(base, {})
                        self.rawendpoints[base] = api
        return endpoints

    def reindent(self, s, indent):
        return s.replace("\n", "\n" + " " * indent)

    def format_json(self, j, indent):
        j = json.dumps(j, indent=4).replace(", \n", ",\n")
        return self.reindent(j, indent)

    def parse_types(self):
        types = self.api['types']
        return types

    def iter_actions(self, endpoint):
        ACTIONS_MAGIC = '/actions/'
        for k, v in endpoint.items():
            if k.startswith(ACTIONS_MAGIC):
                k = k[len(ACTIONS_MAGIC):]
                v = v['post']
                # simplify the raml tree for easier processing
                v['body'] = v['body']['application/json'].get('properties', {})
                yield (k, v)
