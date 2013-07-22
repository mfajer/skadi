import copy
import numpy
import numpy.linalg

class CoordinateMapper(object):
	def __init__(self, reference, snapshot):
		'''Pass a reference dictionary of entity_name: {'x':x, 'y':y} coordinates.'''
		self._reference = copy.deepcopy(reference)
		# Add the cell coordinates into the reference
		for key, val in self._reference.iteritems():
			matching_entities = filter(lambda x: 'DT_BaseEntity.m_iName' in x.state and x.state['DT_BaseEntity.m_iName'] == key, snapshot.instances.itervalues())
			if len(matching_entities) != 1:
				raise UserWarning("Incorrect number of matches (%d)" % len(matching_entities))
			val['cellX'] = matching_entities[0].state['DT_DOTA_BaseNPC.m_cellX']
			val['cellY'] = matching_entities[0].state['DT_DOTA_BaseNPC.m_cellY']
		self._generate_mapping()

	def _generate_mapping(self):
		Ax = numpy.vstack([[v['cellX'] for v in self._reference.itervalues()], numpy.ones(len(self._reference))]).T
		self._scale_x, self._offset_x = numpy.linalg.lstsq(Ax, [v['x'] for v in self._reference.itervalues()])[0]
		Ay = numpy.vstack([[v['cellY'] for v in self._reference.itervalues()], numpy.ones(len(self._reference))]).T
		self._scale_y, self._offset_y = numpy.linalg.lstsq(Ay, [v['y'] for v in self._reference.itervalues()])[0]

	def to_cell(self, mapped_x, mapped_y):
		return ((mapped_x - self._offset_x)/self._scale_x, (mapped_y - self._offset_y)/self._scale_y)

	def to_mapped(self, cell_x, cell_y):
		return (self._scale_x * cell_x + self._offset_x, self._scale_y * cell_y + self._offset_y)

if __name__ == "__main__":
	# Reference frame for in-game dota_camera_setpos (bottom-left corner)
	dota_camera_getpos_ref = {
		'dota_goodguys_tower1_top': {'x':-5461, 'y':2010},
		'dota_goodguys_tower2_top': {'x':-5461, 'y':-683},
		'dota_goodguys_tower1_bot': {'x':5600, 'y':-5927},
		'dota_goodguys_tower2_bot': {'x':29, 'y':-5927},
		'dota_badguys_tower1_top': {'x':-4104, 'y':6030},
		'dota_badguys_tower2_top': {'x':588, 'y':6030},
		'dota_badguys_tower1_bot': {'x':6767, 'y':-1569},
		'dota_badguys_tower2_bot': {'x':6767, 'y':521},
	}
	# Reference frame for 25-megapixel top-down PNG from http://www.reddit.com/r/DotA2/comments/1805d9/the_complete_dota2_map_25_megapixel_resolution/
	hires_map_ref = {
		'dota_goodguys_tower1_top': {'x':655, 'y':1967},
		'dota_goodguys_tower1_mid': {'x':2082, 'y':2967},
		'dota_goodguys_tower1_bot': {'x':4077, 'y':4442},
		'dota_badguys_tower1_top': {'x':1081, 'y':670},
		'dota_badguys_tower1_mid': {'x':2870, 'y':2441},
		'dota_badguys_tower1_bot': {'x':4441, 'y':3071},
	}
	mapper = CoordinateMapper(hires_map_ref, earlytick)

	# Set up the backend for display-less plotting	
	import matplotlib
	matplotlib.rcParams['backend'] = 'Agg'

	# Load the background map
	import matplotlib.image
	background_map = matplotlib.image.imread('../../dota_map.png')

	# Plot the least-squares fitting for the mapping
	import pylab
	pylab.plot([v['cellX'] for v in mapper._reference.values()], [v['x'] for v in mapper._reference.values()], 'bo', label='X')
	line_xs = numpy.arange(min([v['cellX'] for v in mapper._reference.values()]), max([v['cellX'] for v in mapper._reference.values()]))
	pylab.plot(line_xs, line_xs * mapper._scale_x + mapper._offset_x, 'b-', label='LSQ-X')
	pylab.plot([v['cellY'] for v in mapper._reference.values()], [v['y'] for v in mapper._reference.values()], 'ko', label='Y')
	line_ys = numpy.arange(min([v['cellY'] for v in mapper._reference.values()]), max([v['cellY'] for v in mapper._reference.values()]))
	pylab.plot(line_ys, line_ys * mapper._scale_y + mapper._offset_y, 'k-', label='LSQ-Y')
	pylab.xlabel('m_cell')
	pylab.ylabel('pixel')
	pylab.legend(loc='upper left')
	pylab.savefig('lsq.png')
	pylab.close()

	# Plot the xs/ys
	mapped_xs = []
	mapped_ys = []
	for (x, y) in zip(xs, ys):
		mx, my = mapper.to_mapped(x, y)
		mapped_xs.append(mx)
		# Re-orient so the (0,0) is in the radiant corner
		mapped_ys.append(background_map.shape[0] - my)
	# Re-orient so the (0,0) is in the radiant corner
	pylab.imshow(background_map[::-1, :, :])
	pylab.plot(mapped_xs, mapped_ys, 'bo')
	pylab.xlim(0, background_map.shape[1])
	pylab.ylim(0, background_map.shape[0])
	pylab.gca().get_xaxis().set_visible(False)
	pylab.gca().get_yaxis().set_visible(False)
	pylab.savefig('mapped_pos.png')
	pylab.close()
