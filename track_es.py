from collections import OrderedDict
import copy
from skadi.util import mapping

xs = OrderedDict()
ys = OrderedDict()
earlytick = None

for tick_idx, tick in enumerate(demo_index.match.ticks):
	print("Tick %d of %d" % (tick_idx, len(demo_index.match.ticks)))
	replay.tick = tick
	for key, value in replay.snapshot.entities.items():
		if value.template.recv_table.dt == 'DT_DOTA_Unit_Hero_Earthshaker':
			if earlytick is None:
				earlytick = copy.deepcopy(replay.snapshot)
			xs[tick] = value.state['DT_DOTA_BaseNPC.m_cellX'] + value.state['DT_DOTA_BaseNPC.m_vecOrigin'][0] / 128.
			ys[tick] = value.state['DT_DOTA_BaseNPC.m_cellY'] + value.state['DT_DOTA_BaseNPC.m_vecOrigin'][1] / 128.

# Map the x/y coordinates
mapper = mapping.CoordinateMapper(mapping.HIRES_MAP_REF, earlytick)
mapped_xs = []
mapped_ys = []
for (x, y) in zip(xs, ys):
	mx, my = mapper.to_mapped(x, y)
	mapped_xs.append(mx)
	# Re-orient so the (0,0) is in the radiant corner
	mapped_ys.append(background_map.shape[0] - my)
