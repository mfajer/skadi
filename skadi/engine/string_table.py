import collections as c
import copy


def construct(*args):
  return StringTable(*args)


class StringTable(object):
  def __init__(self, name, ent_bits, sz_fixed, sz_bits, ents):
    self.name = name
    self.entry_bits = ent_bits
    self.size_fixed = sz_fixed
    self.size_bits = sz_bits
    self.update_all(ents)

  def get(self, name):
    return self.by_name[name]

  def update_all(self, entries):
    self.by_index = c.OrderedDict()
    self.by_name = c.OrderedDict()

    [self.update(entry) for entry in entries]

  def update(self, entry):
    i, n, d = entry

    self.by_index[i] = (n, d)
    if n:
      self.by_name[n] = (i, d)
