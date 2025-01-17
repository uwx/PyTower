import copy
import json
import logging
import typing
import uuid

import numpy as np

from .connections import ItemConnectionObject
from .util import XYZ, XYZW

ITEMCONNECTIONS_DEFAULT = json.loads('''{
              "Array": {
                "array_type": "StructProperty",
                "value": {
                  "Struct": {
                    "_type": "ItemConnections",
                    "name": "StructProperty",
                    "struct_type": {
                      "Struct": "ItemConnectionData"
                    },
                    "id": "00000000-0000-0000-0000-000000000000",
                    "value": []
                  }
                } 
              }
            }''')


class TowerObject:
    """Tower object

    Represents an object appearing in the Suitebro file. This includes all the sections of the object.
    """

    def __init__(self, item: dict | None = None, properties: dict | None = None, nocopy: bool = False):
        """Initializes TowerObject instance taking in uesave json data

        Args:
            item: The item section parsed, as parsed from tower-unite-suitebro
            properties: The properties section, as parsed from tower-unite-suitebro
            nocopy: If True, then do not deep-copy the item and properties dictionaries
        """
        if nocopy:
            self.item = item
            self.properties = properties
        else:
            self.item = copy.deepcopy(item)
            self.properties = copy.deepcopy(properties)

    def is_canvas(self) -> bool:
        if self.item is None:
            return False

        item_props = self.item['properties']
        return self.get_name().startswith('Canvas') or 'SurfaceMaterial' in item_props or 'URL' in item_props

    def get_name(self) -> str:
        if self.item is None:
            return self.properties['name']
        return self.item['name']

    def get_custom_name(self) -> str:
        if self.item is None or 'ItemCustomName' not in self.item['properties']:
            return ''
        return self.item['properties']['ItemCustomName']['Name']['value']

    def matches_name(self, name) -> bool:
        name = name.casefold()
        return self.get_name().casefold() == name or self.get_custom_name().casefold() == name

    def group_id(self) -> int:
        if self.item is None or 'GroupID' not in self.item['properties']:
            return -1
        return self.item['properties']['GroupID']['Int']['value']

    def set_group_id(self, group_id: int):
        self.item['properties']['GroupID'] = {'Int': {'value': group_id}}
        if self.properties is not None:
            self.properties['properties']['GroupID'] = {'Int': {'value': group_id}}

    # Removes group info from self
    def ungroup(self):
        if self.item is not None and 'GroupID' in self.item['properties']:
            del self.item['properties']['GroupID']

            if self.properties is not None:
                del self.properties['properties']['GroupID']

    def copy(self) -> 'TowerObject':
        copied = TowerObject(item=self.item, properties=self.properties)
        if copied.item is not None:
            copied.item['guid'] = str(uuid.uuid4()).lower()
        return copied

    def guid(self) -> str:
        return self.item['guid']

    def _get_xyz_attr(self, name: str) -> XYZ | None:
        if self.item is None:
            return None
        xyz = self.item[name]
        return np.array([xyz['x'], xyz['y'], xyz['z']]).view(XYZ)

    def _set_xyz_attr(self, name: str, value: XYZ):
        if self.item is None:
            logging.warning(f'Attempted to xyz set {name} on a property-only object!')
            return

        pos = self.item[name]
        pos['x'] = value[0]
        pos['y'] = value[1]
        pos['z'] = value[2]

    def _get_xyzw_attr(self, name: str) -> XYZW | None:
        if self.item is None:
            return None
        xyzw = self.item[name]
        return np.array([xyzw['x'], xyzw['y'], xyzw['z'], xyzw['w']]).view(XYZW)

    def _set_xyzw_attr(self, name: str, value: XYZW):
        if self.item is None:
            logging.warning(f'Attempted to xyzw set {name} on a property-only object!')
            return

        pos = self.item[name]
        pos['x'] = value[0]
        pos['y'] = value[1]
        pos['z'] = value[2]
        pos['w'] = value[3]

    @property
    def position(self) -> XYZ | None:
        """World position"""
        return self._get_xyz_attr('position')

    @position.setter
    def position(self, value: XYZ):
        self._set_xyz_attr('position', value)

        if self.item and self.properties:
            item_props = self.item['properties']
            prop_props = self.properties['properties']

            if 'RespawnLocation' in prop_props:
                translation = prop_props['RespawnLocation']['Struct']['value']['Struct']['Translation']['Struct']
                translation['value']['Vector']['x'] = value[0]
                translation['value']['Vector']['y'] = value[1]
                translation['value']['Vector']['z'] = value[2]

                item_props['RespawnLocation'] = prop_props['RespawnLocation']


    @property
    def rotation(self) -> XYZW | None:
        """Rotation quaternion"""
        return self._get_xyzw_attr('rotation')

    @rotation.setter
    def rotation(self, value: XYZW):
        self._set_xyzw_attr('rotation', value)

        if self.item and self.properties:
            item_props = self.item['properties']
            prop_props = self.properties['properties']

            if 'RespawnLocation' in prop_props:
                rot = prop_props['RespawnLocation']['Struct']['value']['Struct']['Rotation']['Struct']['value']
                rot['Quat']['x'] = value[0]
                rot['Quat']['y'] = value[1]
                rot['Quat']['z'] = value[2]
                rot['Quat']['w'] = value[3]

                item_props['RespawnLocation'] = prop_props['RespawnLocation']

    @property
    def scale(self) -> XYZ | None:
        """Local scale"""
        return self._get_xyz_attr('scale')

    @scale.setter
    def scale(self, value: XYZ):
        self._set_xyz_attr('scale', value)

        if self.properties:
            props = self.properties['properties']

            if 'WorldScale' in props:
                props['WorldScale']['Struct']['value']['Vector']['x'] = value[0]
                props['WorldScale']['Struct']['value']['Vector']['y'] = value[1]
                props['WorldScale']['Struct']['value']['Vector']['z'] = value[2]

                self.item['properties']['WorldScale'] = props['WorldScale']

            if ('RespawnLocation' in props and 'properties' in self.item
                    and 'RespawnLocation' in self.item['properties']):
                scale3d_data = props['RespawnLocation']['Struct']['value']['Struct']['Scale3D']
                scale3d = scale3d_data['Struct']['value']['Vector']
                scale3d['x'] = value[0]
                scale3d['y'] = value[1]
                scale3d['z'] = value[2]

                self.item['properties']['RespawnLocation'] = props['RespawnLocation']

    def _check_connetions(self):
        if self.item is not None and 'ItemConnections' not in self.item.keys():
            self.item['ItemConnections'] = copy.deepcopy(ITEMCONNECTIONS_DEFAULT)

    def add_connection(self, con: ItemConnectionObject):
        assert self.item is not None
        self._check_connetions()

        connections = self.item['properties']['ItemConnections']['Array']['value']['Struct']['value']
        connections.append(con.to_dict())

        if self.properties is not None:
            self.properties['properties']['ItemConnections'] = self.item['properties']['ItemConnections']

    def get_connections(self) -> list[ItemConnectionObject]:
        assert self.item is not None
        self._check_connetions()

        cons = []
        for data in self.item['properties']['ItemConnections']['Array']['value']['Struct']['value']:
            cons.append(ItemConnectionObject(data))

        return cons

    def set_connections(self, cons: list[ItemConnectionObject]):
        assert self.item is not None
        self._check_connetions()

        self.item['properties']['ItemConnections']['Array']['value']['Struct']['value'] \
            = list(map(lambda con: con.to_dict(), cons))

        if self.properties is not None:
            self.properties['properties']['ItemConnections'] = self.item['properties']['ItemConnections']

    def __lt__(self, other):
        if not isinstance(other, TowerObject):
            return False

        if self.item is None and other.item is None:
            # CondoWeather needs to always be first, followed by CondoSettingsManager, then Ultra_Dynamic_Sky?
            if self.properties['name'].startswith('CondoWeather'):
                return True
            elif self.properties['name'].startswith('CondoSettingsManager'):
                return not other.properties['name'].startswith('CondoWeather')
            elif self.properties['name'].startswith('Ultra_Dynamic_Sky'):
                return (not other.properties['name'].startswith('CondoWeather')) and \
                    (not other.properties['name'].startswith('CondoSettingsManager'))

            return self.properties['name'] < other.properties['name']

        if self.item is None:
            return True

        if other.item is None:
            return False

        return self.item['name'] < other.item['name']

    def __repl__(self):
        return f'TowerObject({self.item}, {self.properties})'

    def __str__(self):
        return self.__repl__()
