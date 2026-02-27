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

from __future__ import annotations

import copy
import json
import os
from collections import OrderedDict
from typing import TYPE_CHECKING
from typing import Any

import yaml

if TYPE_CHECKING:
    from collections.abc import Iterator

    from yaml.nodes import MappingNode
    from yaml.nodes import ScalarNode


# minimalistic raml loader. Support !include tags, and mapping as OrderedDict
class RamlLoader(yaml.SafeLoader):
    pass


def construct_include(loader: RamlLoader, node: ScalarNode) -> OrderedDict:
    path = os.path.join(os.path.dirname(loader.stream.name), node.value)
    with open(path, encoding='utf-8') as f:
        return yaml.load(f, Loader=RamlLoader)


def construct_mapping(loader: RamlLoader, node: MappingNode) -> OrderedDict:
    loader.flatten_mapping(node)
    return OrderedDict(loader.construct_pairs(node))


RamlLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)
RamlLoader.add_constructor('!include', construct_include)


class RamlSpec:
    """
    This class loads the raml specification, and expose useful
    aspects of the spec

    Main usage for now is for the doc, but it can be extended to make sure
    raml spec matches other spec implemented in the tests
    """

    def __init__(self) -> None:
        fn = os.path.join(os.path.dirname(__file__), os.pardir, 'spec', 'api.raml')
        with open(fn, encoding='utf-8') as f:
            self.api: OrderedDict[str, Any] = yaml.load(f, Loader=RamlLoader)

        with open(fn, encoding='utf-8') as f:
            self.rawraml = f.read()

        self.endpoints_by_type: dict[str, Any] = {}
        self.rawendpoints: dict[str, Any] = {}
        self.endpoints = self.parse_endpoints({}, "", self.api)
        self.types = self.parse_types()

    def parse_endpoints(
        self,
        endpoints: dict[str, OrderedDict],
        base: str,
        api: OrderedDict[str, Any],
        uriParameters: OrderedDict | None = None,
    ) -> dict[str, OrderedDict]:
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
                        raise RuntimeError(f'Unexpected "is" target {type(_is)}: {_is}')

                    if 'bbget' in _is:
                        try:
                            v['eptype'] = _is['bbget']['bbtype']
                        except TypeError as e:
                            raise RuntimeError(f"Unexpected 'is' target {_is['bbget']}") from e

                        self.endpoints_by_type.setdefault(v['eptype'], {})
                        self.endpoints_by_type[v['eptype']][base] = api

                    if 'bbgetraw' in _is:
                        self.rawendpoints.setdefault(base, {})
                        self.rawendpoints[base] = api
        return endpoints

    def reindent(self, s: str, indent: int) -> str:
        return s.replace("\n", "\n" + " " * indent)

    def format_json(self, j: OrderedDict, indent: int) -> str:
        j_str = json.dumps(j, indent=4).replace(", \n", ",\n")
        return self.reindent(j_str, indent)

    def parse_types(self) -> OrderedDict:
        types = self.api['types']
        return types

    def iter_actions(self, endpoint: OrderedDict) -> Iterator[tuple[str, OrderedDict]]:
        ACTIONS_MAGIC = '/actions/'
        for k, v in endpoint.items():
            if k.startswith(ACTIONS_MAGIC):
                k = k[len(ACTIONS_MAGIC) :]
                v = v['post']
                # simplify the raml tree for easier processing
                v['body'] = v['body']['application/json'].get('properties', {})
                yield (k, v)
