import itertools
import json
import logging
import os
import platform
import sys
from subprocess import Popen, PIPE

from colorama import Fore, Back, Style

from .__config__ import root_directory
from .selection import Selection
from .object import TowerObject

IO_GW_ITEMS = ['AmmoPickup', 'CustomSpawnPoint', 'HealthPickup', 'SDNL_ArmorPickup', 'GW_SDNLOddball', 'GW_SDNLFlag',
               'GW_BallRaceFinish', 'GW_BallRaceSpawn', 'LaserBeam', 'LeverBasic', 'ButtonShapes', 'PhysicsSlot',
               'WeaponPickupIO', 'ButtonCanvas', 'LocationVolumeIO', 'DamageHealVolume', 'BlockingVolume',
               'WaterVolume', 'CommentVolume', 'DialogueVolume', 'GravityVolume', 'ButtonVolume', 'HitTargetVolume',
               'LadderVolume', 'PlayerMovementVolume', 'PostProcessVolume', 'PushVolume', 'SizeVolume',
               'SkyProcessVolume', 'SpawnPointTagVolume', 'TriggerVolume', 'WeaponStripVolume', 'TeleportVolume',
               'GameWorldEvents', 'LaserBeamReciever', 'Mover', 'Counter', 'LogicGateAnd', 'SwitchBoolean',
               'LogicGateNot', 'LogicGateOr', 'LogicGateXor', 'Random', 'Relay', 'Timer', 'Toggle', 'WorldControl',
               'LeverLightSwitch', 'MoverAdvanced', 'MoverPlayerSlide', 'MoverTrain']


class Suitebro:
    """Suitebro file

    Abstraction over the input CondoData/.map file, representing parsed tower-unite-suitebro data

    Attributes:
        objects: The list of TowerObject instances contained in the Suitebro file
    """
    def __init__(self, filename: str, directory: str, data: dict):
        """Instantiates a new Suitebro instance based on the input filename and directory

        Args:
            filename: Name of file
            directory: Path to directory (can be relative or absolute)
            data: The raw json data from tower-unite-suitebro
        """
        self.filename = filename
        self.directory = directory
        self.data: dict = data

        # Parse objects
        prop_section = self.data['properties']
        item_section = self.data['items']
        num_props = len(prop_section)
        num_items = len(item_section)
        self.objects: list[TowerObject | None] = [None] * (num_items + num_props)

        # First get all names present in properties to determine item-only objects. Except for property-only metadata
        #  objects, every property name is <SOME ITEM NAME>_C_###, where ### is the index within the item-type grouping
        prop_names = set()
        for prop_data in prop_section:
            name: str = prop_data['name']
            try:
                name_end = name.rindex('_C_')
                prop_names.add(name[:name_end])
            except ValueError:
                continue

        # This algorithm handles inserting TowerObjects from the (indexed) json by handling three cases:
        #  Case 1: There is an item but no corresponding property
        #  Case 2 (Most likely): There is an item and a corresponding property
        #  Case 3: There is no item and just a property
        item_idx = 0
        prop_idx = 0
        x = 0
        while item_idx < num_items or prop_idx < num_props:
            p = prop_section[prop_idx] if prop_idx < num_props else None
            i = item_section[item_idx] if item_idx < num_items else None
            # print(p['name'] if p is not None else None)
            # print(i['name'] if i is not None else None)
            if i is not None and i['name'] not in prop_names:
                self.objects[x] = TowerObject(item=i, properties=None, nocopy=True)
                item_idx += 1
            elif i is not None and p is not None and p['name'].startswith(i['name']):
                self.objects[x] = TowerObject(item=i, properties=p, nocopy=True)
                item_idx += 1
                prop_idx += 1
            elif p is not None:
                self.objects[x] = TowerObject(item=None, properties=p, nocopy=True)
                prop_idx += 1
            x += 1

        # Now cull Nones at the end of array
        if None in self.objects:
            size = self.objects.index(None)
            self.objects = self.objects[:size]

    def add_object(self, obj: TowerObject):
        """Adds a new object to the Suitebro file

        Args:
            obj: The object to add
        """
        self.objects += [obj]

    def add_objects(self, objs: list[TowerObject]):
        """Adds a list of objects to the Suitebro file

        Args:
            objs: The list of objects to add
        """
        self.objects += objs

    def find_item(self, name: str) -> TowerObject | None:
        """Find a TowerObject by its name

        Args:
            name: The proper name or the nickname of the TowerObject

        Returns:
            The first TowerObject matching the name, if found, or else None

        """
        for obj in self.objects:
            if obj.matches_name(name):
                return obj
        return None

    def get_groups_meta(self):
        return self.data['groups']

    # TODO Definitely a better way to do this
    def get_max_groupid(self):
        sel = Selection(self.objects)
        # Get the max group_id tuple in group and get its id (first slot of tuple)
        return max(sel.groups(), key=lambda group_data: group_data[0])[0]

    def update_groups_meta(self):
        sel = Selection(self.objects)
        group_data = []
        for group_id, group in sel.groups():
            group_data.append({'group_id': group_id, 'item_count': len(group)})
        self.data['groups'] = group_data

    def items(self) -> list[TowerObject]:
        """Lists all non-property TowerObjects

        Returns:
            List containing all of the non-property TowerObject instances in this Suitebro
        """
        return [obj for obj in self.objects if obj.item is not None]

    def inventory_items(self) -> list[TowerObject]:
        """Lists all TowerObject instances that are non-property and are not I/O nor Game-World.

        This is equivalent to getting all items that exist in a player's inventory

        Returns:
            List of TowerObject instances in the Suitebro that exist in a player's Steam inventory
        """
        return [obj for obj in self.objects if obj.item is not None and obj.get_name() not in IO_GW_ITEMS]

    def _item_count(self, objs) -> dict:
        ordered = sorted(objs, key=TowerObject.get_name)
        return {name: len(list(objs)) for name, objs in itertools.groupby(ordered, TowerObject.get_name)}

    def item_count(self) -> dict:
        """Counts the number of items in the Suitebro file

        Returns:
            Dictionary where each key is the proper name of the object and the value is the number of instances
        """
        return self._item_count(self.objects)

    def inventory_count(self) -> dict:
        """Counts the number of inventory items in the Suitebro file

        Returns:
            Dictionary where each key is the proper name of the object and the value is the number of instances
        """
        objs = self.inventory_items()
        return self._item_count(objs)

    # Convert item list back into a dict
    def to_dict(self):
        """Converts the Suitebro object back into a dictionary, formatted in the tower-unite-suitebro style

        Returns:
            Serialized Suitebro representation that can be written to a file using json.dump
        """
        new_dict = {}

        # Update groups based on group ids and info
        self.update_groups_meta()

        for k, v in self.data.items():
            if k != 'items' and k != 'properties':
                new_dict[k] = v

        self.objects.sort()

        num_obj = len(self.objects)
        item_arr = [None] * num_obj
        prop_arr = [None] * num_obj

        item_idx = 0
        prop_idx = 0

        last_name = None
        last_num = 0
        for obj in self.objects:
            if obj.item is not None:
                item_arr[item_idx] = obj.item
                item_idx += 1
            if obj.properties is not None:
                # Name fuckery TODO determine if the naming even matters
                if obj.item is not None:
                    name_split = obj.properties['name'].split('_')
                    root_name = '_'.join(name_split[:-1])

                    if last_name == root_name:
                        last_num += 1
                    else:
                        last_num = 0

                    obj.properties['name'] = root_name + '_' + str(last_num)

                    last_name = root_name

                # Now actually add to prop_arr
                prop_arr[prop_idx] = obj.properties
                prop_idx += 1

        item_arr = item_arr[:item_idx]
        prop_arr = prop_arr[:prop_idx]

        # Finally set new dictionary and return
        new_dict['items'] = item_arr
        new_dict['properties'] = prop_arr
        return new_dict

    def __repl__(self):
        return f'Suitebro({self.data}, {self.objects})'

    def __iter__(self):
        for obj in self.objects:
            yield obj


# _active_saves is a stack
_active_save: Suitebro | None = None


def get_active_save() -> Suitebro | None:
    return _active_save


def get_suitebro_path():
    # For cases when want to build suitebro parser from source, for whatever reason
    from .config import CONFIG, KEY_FROM_SOURCE
    if CONFIG and CONFIG.get(KEY_FROM_SOURCE):
        source_dir = os.path.join(root_directory, 'tower-unite-suitebro')
        if os.path.isdir(source_dir):
            return source_dir
        else:
            print('Error: could not find tower-unite-suitebro. Is suitebro installed in a folder named tower-unite-'
                  'suitebro?', file=sys.stderr)
            sys.exit(1)

    if sys.platform == 'win32':
        subdir = os.path.join(os.path.join('lib', 'win64'), 'tower-unite-save-x86_64-pc-windows-msvc.exe')
    elif sys.platform == 'darwin':
        machine = platform.machine().lower()
        is_arm = machine.startswith('arm') or machine.startswith('aarch') or platform.processor().lower() == 'apple arm'
        if is_arm:
            subdir = os.path.join(os.path.join('lib', 'apple-aarch64'), 'tower-unite-save-aarch64-apple-darwin')
        else:
            subdir = os.path.join(os.path.join('lib', 'apple-x86'), 'tower-unite-save-x86_64-apple-darwin')
    elif sys.platform == 'linux':
        is_docker = False
        with open('/proc/1/cgroup', 'rt') as f:
            for line in f:
                if 'docker' in line:
                    is_docker = True

        if is_docker:
            subdir = os.path.join(os.path.join('lib', 'linux-container'), 'tower-unite-save-x86_64-unknown-linux-musl')
        else:
            subdir = os.path.join(os.path.join('lib', 'linux'), 'tower-unite-save-x86_64-unknown-linux-gnu')
    else:
        print(f'{sys.platform} is not supported :( try running in json-only mode with the -j flag', file=sys.stderr)
        sys.exit(1)

    return os.path.join(root_directory, subdir)


def pretty_path(path: str) -> str:
    relpath = os.path.relpath(path, root_directory)
    abspath = os.path.abspath(path)
    if len(relpath) < len(abspath):
        return relpath
    else:
        return abspath


def run_suitebro_parser(input_path: str, to_save: bool, output_path: str | None = None,
                        overwrite: bool = False) -> bool:
    exe_path = get_suitebro_path()
    process = Popen(f'\"{exe_path}\" {"to-save" if to_save else "to-json"} {"-!" if overwrite else ""}'
                    f' -i \"{input_path}\" -o \"{output_path}\"', stdout=PIPE, shell=True)
    (output, err) = process.communicate()
    for line in output.splitlines(False):
        print(line.decode('ascii'))

    exit_code = process.wait()

    if exit_code != 0:
        logging.error('Suitebro parser did not complete successfully!')
        return False

    print(
        Fore.GREEN + f'Successfully converted {pretty_path(input_path)} to {pretty_path(output_path)}' + Style.RESET_ALL)
    return True


def load_suitebro(filename: str, only_json=False) -> Suitebro:
    abs_filepath = os.path.realpath(filename)
    in_dir = os.path.dirname(abs_filepath)
    json_output_path = os.path.join(in_dir, os.path.basename(abs_filepath) + ".json")

    if not only_json:
        run_suitebro_parser(abs_filepath, False, json_output_path, overwrite=True)

    logging.info('Loading JSON file...')
    with open(json_output_path, 'r') as fd:
        save_json = json.load(fd)

    save = Suitebro(os.path.basename(abs_filepath), in_dir, save_json)

    global _active_save
    _active_save = save

    return save


def save_suitebro(save: Suitebro, filename: str, only_json=False):
    abs_filepath = os.path.realpath(filename)
    out_dir = os.path.dirname(abs_filepath)
    json_final_path = os.path.join(save.directory, f'{filename}.json')
    final_output_path = os.path.join(out_dir, f'{filename}')

    with open(json_final_path, 'w') as fd:
        json.dump(save.to_dict(), fd, indent=2)

    # Finally run!
    if not only_json:
        run_suitebro_parser(json_final_path, True, final_output_path, overwrite=True)
