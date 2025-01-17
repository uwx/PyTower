import itertools
import math
import random

import numpy as np

from .object import TowerObject

from abc import ABC, abstractmethod
import re

from .util import XYZ


class Selection(set[TowerObject]):
    @staticmethod
    def _group_key(obj: TowerObject):
        return obj.group_id()

    def groups(self) -> set[tuple[int, 'Selection']]:
        data = sorted(filter(lambda obj: obj.group_id() >= 0, self), key=Selection._group_key)
        return {(group_id, Selection(group)) for group_id, group in itertools.groupby(data, Selection._group_key)}

    def ungrouped(self) -> 'Selection':
        return Selection({obj for obj in self if obj.group_id() < 0})

    def destroy_groups(self):
        for obj in self:
            obj.ungroup()

    def get(self) -> TowerObject:
        return next(iter(self))

    def __add__(self, other: 'Selection') -> 'Selection':
        if not isinstance(other, Selection):
            raise ValueError(f'Cannot add Selection with {type(other)}!')

        return Selection(self.union(other))

    def __iadd__(self, other: 'Selection') -> None:
        if not isinstance(other, Selection):
            raise ValueError(f'Cannot add Selection with {type(other)}!')

        self.update(other)

    def __mul__(self, other: 'Selection') -> 'Selection':
        if not isinstance(other, Selection):
            raise ValueError(f'Cannot multiply Selection with {type(other)}!')

        return Selection(self.intersection(other))

    def __imul__(self, other: 'Selection') -> None:
        if not isinstance(other, Selection):
            raise ValueError(f'Cannot multiply Selection with {type(other)}!')

        self.intersection_update(other)

    def __hash__(self):
        return hash(tuple(self))


class Selector(ABC):
    def __init__(self, name):
        self.name = name

    # Selectors take in a Selection and output a new Selection.
    # Can think of these Selectors operating on the set of everything, and selecting a subset.
    # But nothing's stopping you from then selecting on that subset, and so on, further and further refining the
    #  selection using Selector objects.
    @abstractmethod
    def select(self, everything: Selection) -> Selection:
        pass


class NameSelector(Selector):
    def __init__(self, select_name):
        super().__init__('NameSelector')
        self.select_name = select_name.casefold()

    def select(self, everything: Selection) -> Selection:
        return Selection({obj for obj in everything if obj.matches_name(self.select_name)})


class CustomNameSelector(Selector):
    def __init__(self, select_name):
        super().__init__('CustomNameSelector')
        self.select_name = select_name.casefold()

    def select(self, everything: Selection) -> Selection:
        return Selection({obj for obj in everything if obj.get_custom_name().casefold() == self.select_name})


class ObjectNameSelector(Selector):
    def __init__(self, select_name):
        super().__init__('ObjectNameSelector')
        self.select_name = select_name.casefold()

    def select(self, everything: Selection) -> Selection:
        return Selection({obj for obj in everything if obj.get_name().casefold() == self.select_name})


class RegexSelector(Selector):
    def __init__(self, pattern: str):
        super().__init__('RegexSelector')
        self.pattern = re.compile(pattern.casefold())

    def select(self, everything: Selection) -> Selection:
        return Selection({obj for obj in everything if self.pattern.match(obj.get_name().casefold())
                          or self.pattern.match(obj.get_custom_name().casefold())})


class GroupSelector(Selector):
    def __init__(self, group_id):
        super().__init__('GroupSelector')
        self.group_id = group_id

    def select(self, everything: Selection) -> Selection:
        return Selection({obj for obj in everything if obj.group_id() == self.group_id})


class ItemSelector(Selector):
    def __init__(self):
        super().__init__('ItemSelector')

    def select(self, everything: Selection) -> Selection:
        return Selection({obj for obj in everything if obj.item is not None})


class EverythingSelector(Selector):
    def __init__(self):
        super().__init__('EverythingSelector')

    def select(self, everything: Selection) -> Selection:
        return everything


class NothingSelector(Selector):
    def __init__(self):
        super().__init__('NothingSelector')

    def select(self, everything: Selection) -> Selection:
        return Selection()


class PercentSelector(Selector):
    def __init__(self, percentage):
        super().__init__('PercentSelector')
        self.percentage = percentage

    def select(self, everything: Selection) -> Selection:
        sequence = list(everything)
        random.shuffle(sequence)
        cutoff = int(len(sequence) * self.percentage / 100 + 0.5)
        return Selection(sequence[0:cutoff])


class TakeSelector(Selector):
    def __init__(self, number):
        super().__init__('TakeSelector')
        self.number = number

    def select(self, everything: Selection) -> Selection:
        sequence = list(everything)
        random.shuffle(sequence)
        return Selection(sequence[0:self.number])


class RandomSelector(Selector):
    def __init__(self, probability):
        super().__init__('RandomSelector')
        self.probability = probability

    def select(self, everything: Selection) -> Selection:
        return Selection({obj for obj in everything if random.uniform(0, 1) <= self.probability})


class BoxSelector(Selector):
    def __init__(self, pos1: XYZ, pos2: XYZ):
        super().__init__('BoxSelector')
        self.min_pos = XYZ.min(pos1, pos2)
        self.max_pos = XYZ.max(pos1, pos2)

    def _contains(self, pos: XYZ):
        return pos == pos.clamp(self.min_pos, self.max_pos)

    def select(self, everything: Selection) -> Selection:
        return Selection({obj for obj in everything if self._contains(obj.position)})


class SphereSelector(Selector):
    def __init__(self, center: XYZ, radius: float):
        super().__init__('SphereSelector')
        self.center = center
        self.radius = radius

    def _contains(self, pos: XYZ):
        return self.center.distance(pos) < self.radius

    def select(self, everything: Selection) -> Selection:
        return Selection({obj for obj in everything if self._contains(obj.position)})
