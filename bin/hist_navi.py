#!/usr/bin/env python

import io
import optparse
import os
import sys

pwd = os.path.dirname(__file__)
root = os.path.join(pwd, '..')
sys.path.append(root)

from collections import OrderedDict
from skadi import demo
from skadi.util import mapping
import numpy

option_parser = optparse.OptionParser()
(options, args) = option_parser.parse_args()

path = os.path.join(root, args[0])

print '> opening {0}'.format(os.path.basename(path))

with io.open(path, 'r+b') as infile:
	replay = demo.construct(infile)

	mapper = None
	rulesid = None
	navi_teamid = None
	navi_heroids = set()
	navi_xs = []
	navi_ys = []

	# TESTING
	towerids = set()
	tower_xs = []
	tower_ys = []

	for tick, string_tables, entities in replay.stream(tick=0):
		print 'at tick {0}: {1} entities'.format(tick, len(entities))
		# Make sure the game has not ended already
		if rulesid is None:
				for key, (cls, serial, state) in entities.iteritems():
					if replay.recv_tables[cls].dt == u'DT_DOTAGamerulesProxy':
						rulesid = key
						break
		if rulesid:
			if entities[rulesid][2]['DT_DOTAGamerules.m_flGameEndTime'] > 0: break
		# Currently assuming that the key for a hero does not change
		# Alternatively we can do this every tick
		if navi_teamid is None:
			for key, (cls, serial, state) in entities.iteritems():
				if replay.recv_tables[cls].dt == u'DT_DOTATeam' and state['DT_Team.m_szTeamname'] == 'Natus Vincere':
					navi_teamid = state['DT_Team.m_iTeamNum']
					break
		if navi_teamid:
			if len(navi_heroids) < 5:
				# Find the DT_DOTA_PlayerResource entity
				resourceid = None
				for key, (cls, serial, state) in entities.iteritems():
					if replay.recv_tables[cls].dt == u'DT_DOTA_PlayerResource':
						resourceid = key
						break
				if resourceid is not None:
					navi_playerindices = []
					for idx in range(10):
						key = 'm_iPlayerTeams.%04d' % idx
						if entities[resourceid][2][key] == navi_teamid:
							navi_playerindices.append(idx)
					for idx in navi_playerindices:
						key = 'm_hSelectedHero.%04d' % idx
						heroid = entities[resourceid][2][key] & 0x7ff
						# Make sure it is actually in entities instead of 2047 (outside of the entities indexing)
						if heroid in entities:
							navi_heroids.add(heroid)
				# TESTING
				for key, (cls, serial, state) in entities.iteritems():
					if replay.recv_tables[cls].dt == u'DT_DOTA_BaseNPC_Tower':
						towerids.add(key)
		# Start grabbing the positions
		if len(navi_heroids) == 5 :
			for heroid in navi_heroids:
				# Only take the coordinates if the hero is currently alive
				if entities[heroid][2]['DT_DOTA_BaseNPC.m_lifeState'] == 0:
					navi_xs.append(entities[heroid][2]['DT_DOTA_BaseNPC.m_cellX'] + entities[heroid][2]['DT_DOTA_BaseNPC.m_vecOrigin'][0]/128.)
					navi_ys.append(entities[heroid][2]['DT_DOTA_BaseNPC.m_cellY'] + entities[heroid][2]['DT_DOTA_BaseNPC.m_vecOrigin'][1]/128.)
			to_remove = []
			for towerid in towerids:
				if towerid in entities:
					tower_xs.append(entities[towerid][2]['DT_DOTA_BaseNPC.m_cellX'] + entities[towerid][2]['DT_DOTA_BaseNPC.m_vecOrigin'][0]/128.)
					tower_ys.append(entities[towerid][2]['DT_DOTA_BaseNPC.m_cellY'] + entities[towerid][2]['DT_DOTA_BaseNPC.m_vecOrigin'][1]/128.)
				else:
					to_remove.append(towerid)
			for towerid in to_remove:
				towerids.remove(towerid)
			# If there is no mapper, make it (not sure when the towers are actually placed)
			if mapper is None:
				mapper = mapping.CoordinateMapper(mapping.HIRES_MAP_REF, entities)

# At this point we should have a the mapper and all of the positions

# Load the background map
import pylab
import matplotlib
import matplotlib.image
import scipy.ndimage
background_map = matplotlib.image.imread('dota_map.png')
# Grayscale the image so the contourf shows up more clearly
def rgb2gray(rgb):
	return numpy.dot(rgb[..., :3], (0.299, 0.587, 0.144))
background_map = rgb2gray(background_map)

# Plot the xs/ys
mapped_xs = []
mapped_ys = []
for (x, y) in zip(navi_xs, navi_ys):
	mx, my = mapper.to_mapped(x, y)
	mapped_xs.append(mx)
	mapped_ys.append(my)
cmap_with_alpha = matplotlib.colors.LinearSegmentedColormap('OrangeRedAlpha', {'red': ((0.0, 1.0, 1.0), (1.0, 0.5, 0.5)),
								'green': ((0.0, 0.55, 0.55), (1.0, 0.15, 0.15)),
								'blue': ((0.0, 0.23, 0.23), (1.0, 0.0, 0.0)),
								'alpha': ((0.0, 0.0, 0.0), (0.05, 0.0, 0.0), (0.25, 0.5, 0.5), (1.0, 1.0, 1.0))})
# Do a pixel-wide histogram followed by a strong Gaussian blur
xedges = numpy.arange(0, background_map.shape[0], 1)
yedges = numpy.arange(0, background_map.shape[1], 1)
H, xedges, yedges = numpy.histogram2d(mapped_xs, mapped_ys, bins=(xedges, yedges))
H = scipy.ndimage.gaussian_filter(H, sigma=50)
X, Y = 0.5*(xedges[1:]+xedges[:-1]), 0.5*(yedges[1:]+yedges[:-1])
# Re-orient so the (0,0) is in the radiant corner
pylab.imshow(background_map[::-1, :], origin='lower', cmap=pylab.cm.gray)
#pylab.contourf(X, Y, H.transpose(), 10, cmap=cmap_with_alpha)
pylab.contourf(X, Y, numpy.log10(H.transpose()+1), 10, cmap=cmap_with_alpha)
pylab.xlim(0, background_map.shape[1])
pylab.ylim(0, background_map.shape[0])
pylab.gca().get_xaxis().set_visible(False)
pylab.gca().get_yaxis().set_visible(False)
pylab.tight_layout(0)
pylab.savefig('mapped_hist.png')
pylab.close()

