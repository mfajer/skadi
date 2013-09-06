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
from skadi import demo
from skadi.util import mapping
import numpy
import pylab
import matplotlib
import matplotlib.image
import scipy.ndimage
import scipy.sparse
import scipy.io

parser = argparse.ArgumentParser()
parser.add_argument('basedir', help='Base directory to recursively search for replays')
args = parser.parse_args()

team_id = 111474
team_name = None
player_id = 76561197964182156L
player_name = None
hero_name = 'npc_dota_hero_naga_siren'
window_size = 300
radiant_hists = {}
dire_hists = {}
radiant_num = {}
dire_num = {}
mapper = None
MAX_COORD_INTEGER = 16384

# Load the background map
background_map = matplotlib.image.imread('dota_map.png')
# Grayscale the image so the contourf shows up more clearly
def rgb2gray(rgb):
	return numpy.dot(rgb[..., :3], (0.299, 0.587, 0.144))
background_map = rgb2gray(background_map)
xedges = numpy.arange(0, background_map.shape[0], 1)
yedges = numpy.arange(0, background_map.shape[1], 1)

print '> Searching {0} for replays containing team {1}'.format(args.basedir, team_id)
for (dirpath, dirnames, fnames) in os.walk(args.basedir):
	for fname in filter(lambda x: os.path.splitext(x)[-1] == '.dem', fnames):
		path = os.path.join(dirpath, fname)
		print '> opening {0}'.format(path)

		replay = demo.construct(path)

		team_num = None
		team_num = 2 if replay.file_info.game_info.dota.radiant_team_id == team_id else team_num
		team_num = 3 if replay.file_info.game_info.dota.dire_team_id == team_id else team_num
		if team_num is None:
			print '>> Did not find team {0}, skipping'.format(team_name or team_id)
			continue
		elif team_name is None:
			team_name = replay.file_info.game_info.dota.radiant_team_tag if team_num == 2 else team_name
			team_name = replay.file_info.game_info.dota.dire_team_tag if team_num == 3 else team_name

		for player_idx, player in enumerate(replay.file_info.game_info.dota.player_info):
			if player.game_team == team_num and player.steamid == player_id:
				player_name = player_name or player.player_name.replace(' ', '_')
				break
		if hero_name and hero_name != player.hero_name:
			print '>> Player {0} is on {1}, not {2}'.format(player_name, player.hero_name, hero_name)
			continue

		xs = []
		ys = []
		hero_ehandle = None

		current_window = 0.0
		next_window = window_size
		# TODO: try to estimate a better tick to start at
		for tick, user_msgs, game_evts, world, modifiers in replay.stream(tick=0):
			# Make sure the game has not ended already
			_, gamerules = world.find_by_dt('DT_DOTAGamerulesProxy')
			if gamerules[(u'DT_DOTAGamerulesProxy', u'DT_DOTAGamerules.m_nGameState')] < 4: continue
			if gamerules[(u'DT_DOTAGamerulesProxy', u'DT_DOTAGamerules.m_nGameState')] > 5: break
			# Find the hero entity once
			if hero_ehandle is None:
				_, presource = world.find_by_dt(u'DT_DOTA_PlayerResource')
				hero_ehandle = presource[('DT_DOTA_PlayerResource', 'm_hSelectedHero.%04d' % player_idx)]
				hero_dt = world.fetch_recv_table(hero_ehandle).dt
				print '>> Found player {0} on {1}'.format(player_name, hero_dt)
			# Make sure the game is not currently paused
			if gamerules[(u'DT_DOTAGamerulesProxy', 'DT_DOTAGamerules.m_bGamePaused')] != 0: continue
			# Add the positions to the correct window and change windows
			game_time = gamerules[(u'DT_DOTAGamerulesProxy', 'DT_DOTAGamerules.m_fGameTime')]
			gamestart_time = gamerules[(u'DT_DOTAGamerulesProxy', 'DT_DOTAGamerules.m_flGameStartTime')]
			if gamestart_time > 0 and (game_time - gamestart_time) > next_window:
				hist, _, _ = numpy.histogram2d(xs, ys, bins=(xedges, yedges))
				window_key = '{0:05.1f}-{1:05.1f}'.format(current_window/60, next_window/60)
				# Add the positions to the right team
				if team_num == 2:
					radiant_hists[window_key]  = radiant_hists.get(window_key, 0) + hist
					radiant_num[window_key]  = radiant_num.get(window_key, 0) + 1
				elif team_num == 3:
					dire_hists[window_key]  = dire_hists.get(window_key, 0) + hist
					dire_num[window_key]  = dire_num.get(window_key, 0) + 1
				xs, ys = [], []
				current_window = next_window
				next_window += window_size
			# If there is no mapper, make it (not sure when the towers are actually placed)
			if mapper is None:
				mapper = mapping.CoordinateMapper(mapping.HIRES_MAP_REF, world)
			# Only take the coordinates if the hero is currently alive
			hero = world.find(hero_ehandle)
			if hero[('DT_DOTA_BaseNPC', 'm_lifeState')] == 0:
				cellwidth = 1 << hero[(u'DT_BaseEntity', u'm_cellbits')]
				x = (hero[('DT_DOTA_BaseNPC', 'm_cellX')] * cellwidth) - MAX_COORD_INTEGER + hero[('DT_DOTA_BaseNPC', 'm_vecOrigin')][0]/128.
				y = (hero[('DT_DOTA_BaseNPC', 'm_cellY')] * cellwidth) - MAX_COORD_INTEGER + hero[('DT_DOTA_BaseNPC', 'm_vecOrigin')][1]/128.
				mx, my = mapper.to_mapped(x, y)
				xs.append(mx)
				ys.append(my)

print '> Finished parsing demos, plotting now'

# Save the (sparse) data in case we fail miserably during plotting
for key, hist in radiant_hists.items():
	fname = '{0}_{1}_{2}_radiant_{3}_{4}.mtx'.format(team_name, player_name, hero_name, key, radiant_num[key])
	scipy.io.mmwrite(fname, scipy.spares.lil_matrix(hist, dtype=int))
for key, hist in dire_hists.items():
	fname = '{0}_{1}_{2}_dire_{3}_{4}.mtx'.format(team_name, player_name, hero_name, key, dire_num[key])
	scipy.io.mmwrite(fname, scipy.spares.lil_matrix(hist, dtype=int))

# Plot the xs/ys
blue_alpha = matplotlib.colors.LinearSegmentedColormap('BlueAlpha', {'red': ((0.0, 0.42, 0.42), (1.0, 0.03, 0.03)),
								'green': ((0.0, 0.68, 0.68), (1.0, 0.19, 0.19)),
								'blue': ((0.0, 0.84, 0.84), (1.0, 0.42, 0.42)),
								'alpha': ((0.0, 0.0, 0.0), (0.1, 0.0, 0.0), (0.2, 0.5, 0.5), (1.0, 1.0, 1.0))})
orange_alpha = matplotlib.colors.LinearSegmentedColormap('OrangeAlpha', {'red': ((0.0, 1.0, 1.0), (1.0, 0.5, 0.5)),
								'green': ((0.0, 0.55, 0.55), (1.0, 0.15, 0.15)),
								'blue': ((0.0, 0.23, 0.23), (1.0, 0.0, 0.0)),
								'alpha': ((0.0, 0.0, 0.0), (0.1, 0.0, 0.0), (0.2, 0.5, 0.5), (1.0, 1.0, 1.0))})

X, Y = 0.5*(xedges[1:]+xedges[:-1]), 0.5*(yedges[1:]+yedges[:-1])
for key, hist in radiant_hists.items():
	# Do a pixel-wide histogram followed by a strong Gaussian blur
	hist = scipy.ndimage.gaussian_filter(hist, sigma=50)
	# Re-orient so the (0,0) is in the radiant corner
	pylab.clf()
	pylab.imshow(background_map[::-1, :], origin='lower', cmap=pylab.cm.gray)
	pylab.contourf(X, Y, hist.transpose(), 10, cmap=blue_alpha)
	pylab.xlim(0, background_map.shape[1])
	pylab.ylim(0, background_map.shape[0])
	pylab.gca().get_xaxis().set_visible(False)
	pylab.gca().get_yaxis().set_visible(False)
	pylab.title('{0} minutes, {1} games'.format(key, radiant_num[key]))
	pylab.tight_layout(0)
	fname = '{0}_{1}_{2}_radiant_{3}_{4}.png'.format(team_name, player_name, hero_name, key, radiant_num[key])
	pylab.savefig(os.path.join(args.basedir, fname))
for key, hist in dire_hists.items():
	# Do a pixel-wide histogram followed by a strong Gaussian blur
	hist = scipy.ndimage.gaussian_filter(hist, sigma=50)
	# Re-orient so the (0,0) is in the radiant corner
	pylab.clf()
	pylab.imshow(background_map[::-1, :], origin='lower', cmap=pylab.cm.gray)
	pylab.contourf(X, Y, hist.transpose(), 10, cmap=orange_alpha)
	pylab.xlim(0, background_map.shape[1])
	pylab.ylim(0, background_map.shape[0])
	pylab.gca().get_xaxis().set_visible(False)
	pylab.gca().get_yaxis().set_visible(False)
	pylab.title('{0} minutes, {1} games'.format(key, dire_num[key]))
	pylab.tight_layout(0)
	fname = '{0}_{1}_{2}_dire_{3}_{4}.png'.format(team_name, player_name, hero_name, key, dire_num[key])
	pylab.savefig(os.path.join(args.basedir, fname))
