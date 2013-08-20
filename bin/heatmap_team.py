#!/usr/bin/env python

import io
import glob
import argparse
import os
import sys

pwd = os.path.dirname(__file__)
root = os.path.join(pwd, '..')
sys.path.append(root)

from collections import OrderedDict
from skadi.replay import demo
from skadi.util import mapping
import numpy

parser = argparse.ArgumentParser()
parser.add_argument('basedir', help='Base directory to recursively search for replays')
parser.add_argument('--team', default='Natus Vincere', help='Team name')
args = parser.parse_args()

team_name = args.team
radiant_xs = []
radiant_ys = []
dire_xs = []
dire_ys = []
mapper = None

print '> Searching {0} for replays containing team {1}'.format(args.basedir, team_name)
for (dirpath, dirnames, fnames) in os.walk(args.basedir):
	for fname in filter(lambda x: os.path.splitext(x)[-1] == '.dem', fnames):
		path = os.path.join(dirpath, fname)
		print '> opening {0}'.format(os.path.basename(path))

		with io.open(path, 'r+b') as infile:
			replay = demo.construct(infile)

			team_num = None
			hero_ehandles = set()
			xs = []
			ys = []

			for tick, string_tables, world in replay.stream(tick=0):
				# Make sure the specific team is involved
				if team_num is None:
					for ehandle, state in world.find_all_by_dt('DT_DOTATeam').iteritems():
						if state[('DT_Team', 'm_szTeamname')] == team_name:
							team_num = state[('DT_Team', 'm_iTeamNum')]
							print '>> Found {0}, processing'.format(team_name)
							break
				# Stop looking at this replay if our team is not
				if team_num is None:
					print '>> Did not find {0}, skipping'.format(team_name)
					break
				# Make sure the game has not ended already
				_, gamerules = world.find_by_dt('DT_DOTAGamerulesProxy')
				if gamerules[('DT_DOTAGamerules', 'm_flGameEndTime')] > 0: break
				# Currently assuming that the key for a hero does not change
				# Alternatively we can do this every tick
				if len(hero_ehandles) < 5:
					# Find the DT_DOTA_PlayerResource entity
					player_resource = world.find_by_dt('DT_DOTA_PlayerResource')[1]
					player_indices = []
					for idx in range(10):
						key = ('m_iPlayerTeams', '%04d' % idx)
						if player_resource[key] == team_num:
							player_indices.append(idx)
					for idx in player_indices:
						key = ('m_hSelectedHero', '%04d' % idx)
						hero_ehandle = player_resource[key]
						# Make sure it is actually in entities instead of 2047 (outside of the entities indexing)
						# HOW TO DO THIS IN THE NEW CODE?
						try:
							world.find(hero_ehandle)
							hero_ehandles.add(hero_ehandle)
						except KeyError:
							pass
				# Start grabbing the positions
				if len(hero_ehandles) == 5 :
					for ehandle in hero_ehandles:
						# Only take the coordinates if the hero is currently alive
						hero = world.find(ehandle)
						if hero[('DT_DOTA_BaseNPC', 'm_lifeState')] == 0:
							xs.append(hero[('DT_DOTA_BaseNPC', 'm_cellX')] + hero[('DT_DOTA_BaseNPC', 'm_vecOrigin')][0]/128.)
							ys.append(hero[('DT_DOTA_BaseNPC', 'm_cellY')] + hero[('DT_DOTA_BaseNPC', 'm_vecOrigin')][1]/128.)
					# If there is no mapper, make it (not sure when the towers are actually placed)
					if mapper is None:
						mapper = mapping.CoordinateMapper(mapping.HIRES_MAP_REF, world)
		# Add the positions to the right team
		if team_num == 2:
			radiant_xs.extend(xs)
			radiant_ys.extend(ys)
		elif team_num == 3:
			dire_xs.extend(xs)
			dire_ys.extend(ys)

print '> Finished parsing demos, plotting now'
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
radiant_mapped_xs = []
radiant_mapped_ys = []
for (x, y) in zip(radiant_xs, radiant_ys):
	mx, my = mapper.to_mapped(x, y)
	radiant_mapped_xs.append(mx)
	radiant_mapped_ys.append(my)
dire_mapped_xs = []
dire_mapped_ys = []
for (x, y) in zip(dire_xs, dire_ys):
	mx, my = mapper.to_mapped(x, y)
	dire_mapped_xs.append(mx)
	dire_mapped_ys.append(my)
blue_alpha = matplotlib.colors.LinearSegmentedColormap('BlueAlpha', {'red': ((0.0, 0.42, 0.42), (1.0, 0.03, 0.03)),
								'green': ((0.0, 0.68, 0.68), (1.0, 0.19, 0.19)),
								'blue': ((0.0, 0.84, 0.84), (1.0, 0.42, 0.42)),
								'alpha': ((0.0, 0.0, 0.0), (0.05, 0.0, 0.0), (0.10, 0.5, 0.5), (1.0, 1.0, 1.0))})
orange_alpha = matplotlib.colors.LinearSegmentedColormap('OrangeAlpha', {'red': ((0.0, 1.0, 1.0), (1.0, 0.5, 0.5)),
								'green': ((0.0, 0.55, 0.55), (1.0, 0.15, 0.15)),
								'blue': ((0.0, 0.23, 0.23), (1.0, 0.0, 0.0)),
								'alpha': ((0.0, 0.0, 0.0), (0.05, 0.0, 0.0), (0.10, 0.5, 0.5), (1.0, 1.0, 1.0))})
# Do a pixel-wide histogram followed by a strong Gaussian blur
xedges = numpy.arange(0, background_map.shape[0], 1)
yedges = numpy.arange(0, background_map.shape[1], 1)
radiant_H, xedges, yedges = numpy.histogram2d(radiant_mapped_xs, radiant_mapped_ys, bins=(xedges, yedges))
numpy.savetxt('{0}_raw_radiant.dat'.format(args.team.lower().replace(' ', '_')), radiant_H)
radiant_H = scipy.ndimage.gaussian_filter(radiant_H, sigma=50)
dire_H, xedges, yedges = numpy.histogram2d(dire_mapped_xs, dire_mapped_ys, bins=(xedges, yedges))
numpy.savetxt('{0}_raw_dire.dat'.format(args.team.lower().replace(' ', '_')), dire_H)
dire_H = scipy.ndimage.gaussian_filter(dire_H, sigma=50)
X, Y = 0.5*(xedges[1:]+xedges[:-1]), 0.5*(yedges[1:]+yedges[:-1])
# Re-orient so the (0,0) is in the radiant corner
pylab.imshow(background_map[::-1, :], origin='lower', cmap=pylab.cm.gray)
if len(radiant_xs):
	pylab.contourf(X, Y, numpy.log10(radiant_H.transpose()+1), 10, cmap=blue_alpha)
if len(dire_xs):
	pylab.contourf(X, Y, numpy.log10(dire_H.transpose()+1), 10, cmap=orange_alpha)
pylab.xlim(0, background_map.shape[1])
pylab.ylim(0, background_map.shape[0])
pylab.gca().get_xaxis().set_visible(False)
pylab.gca().get_yaxis().set_visible(False)
pylab.tight_layout(0)
pylab.savefig('{0}_heatmap.png'.format(args.team.lower().replace(' ', '_')))
pylab.close()

