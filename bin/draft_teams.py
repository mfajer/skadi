#!/usr/bin/env python

import io
import argparse
import os
import sys

pwd = os.path.dirname(__file__)
root = os.path.join(pwd, '..')
sys.path.append(root)

from collections import OrderedDict
from skadi.replay import demo
from skadi.util import mapping

parser = argparse.ArgumentParser()
parser.add_argument('basedir', help='Base directory to recursively search for replays')
args = parser.parse_args()

team_pickbans = {}
tournament_tags = {}

print '> Searching {0} for CM replays'.format(args.basedir)
demo_paths = []
for (dirpath, dirnames, fnames) in os.walk(args.basedir):
	for fname in filter(lambda x: os.path.splitext(x)[-1] == '.dem', fnames):
		path = os.path.join(dirpath, fname)
		demo_paths.append(path)
print '> Found {0:d} replays to process'.format(len(demo_paths))

for idx, path in enumerate(demo_paths):
	print '> opening {0} ({1:d}/{2:d})'.format(os.path.basename(path), idx+1, len(demo_paths))

	with io.open(path, 'r+b') as infile:
		replay = demo.construct(infile)

		last_pickban = None
		last_time = None
		last_team = None
		pick_counter = {2: 0, 3: 0}
		ban_counter = {2: 0, 3: 0}
		team_tags = {}
		draft_duration = {}

		for tick, string_tables, world in replay.stream(tick=0):
			# Grab the team tags
			if len(team_tags) < 2:
				for ehandle, state in world.find_all_by_dt('DT_DOTATeam').iteritems():
					team_num = state[(u'DT_Team', u'm_iTeamNum')]
					team_tag = state[(u'DT_DOTATeam', u'm_szTag')]
					team_tourny_id = state[(u'DT_DOTATeam', u'm_unTournamentTeamID')]
					if team_num in (2, 3):
						if team_tourny_id:
							team_tags[team_num] = tournament_tags.setdefault(team_tourny_id, team_tag)
						else:
							team_tags[team_num] = team_tag
			# Process the picks/bans
			_, gamerules = world.find_by_dt('DT_DOTAGamerulesProxy')
			current_state = gamerules[('DT_DOTAGamerules', 'm_nGameState')]
			current_time = gamerules[(u'DT_DOTAGamerules', u'm_fGameTime')]
			current_team = gamerules[(u'DT_DOTAGamerules', u'm_iActiveTeam')]
			current_pickban = gamerules[(u'DT_DOTAGamerules', u'm_nHeroPickState')]
			# CM game?
			if gamerules[('DT_DOTAGamerules', 'm_iGameMode')] != 2:
				print '>> Not a CM match'
				break
			# Still drafting?
			if current_state > 2:
				# Add the total draft durations now
				for team_id in (2, 3):
					starting_key = 'First pick' if gamerules[(u'DT_DOTAGamerules', u'm_iStartingTeam')] == team_id else 'Second pick'
					side_key = 'Radiant' if team_id == 2 else 'Dire'
					combined_key = '%s - %s' % (side_key, starting_key)
					pickban_dict = team_pickbans.setdefault(team_tags[team_id], {}).setdefault(combined_key, {})
					pickban_dict.setdefault('total', []).append(draft_duration[team_id])
				break
			if current_state == 1: continue
			# First pass
			if current_pickban != last_pickban:
				if last_pickban is not None:
					duration = current_time - last_time
					starting_key = 'First pick' if gamerules[(u'DT_DOTAGamerules', u'm_iStartingTeam')] == last_team else 'Second pick'
					side_key = 'Radiant' if last_team == 2 else 'Dire'
					combined_key = '%s - %s' % (side_key, starting_key)
					if 6 <= last_pickban <= 15:
						ban_counter[last_team] += 1
						pickban_key = 'ban-%d' % ban_counter[last_team]
					elif 16 <= last_pickban <= 25:
						pick_counter[last_team] += 1
						pickban_key = 'pick-%d' % pick_counter[last_team]
					else:
						raise UserWarning("Unkown m_nHeroPickState: %d" % last_pickban)
					pickban_dict = team_pickbans.setdefault(team_tags[last_team], {}).setdefault(combined_key, {})
					pickban_dict.setdefault(pickban_key, []).append(duration)
					draft_duration[last_team] = draft_duration.get(last_team, 0) + duration
				last_time = current_time
				last_pickban = current_pickban
				last_team = current_team

# Now plot the data
import numpy
import pylab

pickban_order = ('ban-1', 'ban-2', 'pick-1', 'pick-2', 'ban-3', 'ban-4', 'pick-3', 'pick-4', 'ban-5', 'pick-5')
filter_keys = ('Radiant - First pick', 'Radiant - Second pick', 'Dire - First pick', 'Dire - Second pick')
combined_filter_keys = ('Radiant', 'Dire', 'First pick', 'Second pick')

# First the individual team analysis
for tag, pickbans in team_pickbans.items():
	pylab.figure()
	for idx, filter_key in enumerate(filter_keys):
		pylab.subplot(2, 2, idx+1)
		num_samples = 0
		if filter_key in pickbans:
			data = numpy.vstack([pickbans[filter_key][pickban_key] for pickban_key in pickban_order]).transpose()
			num_samples = data.shape[0]
			if num_samples > 1:
				pylab.boxplot(data, whis=1000)
		pylab.title('%s - %s (%d)' % (tag, filter_key, num_samples))
		pylab.xticks(range(1, 11), pickban_order, rotation=-90)
		pylab.ylabel('Seconds to pick/ban')
		pylab.ylim(0, 130)
	fname = 'draft_%s_pick_and_side.png' % tag.lower().replace(' ', '_')
	pylab.tight_layout()
	pylab.savefig(fname)
	pylab.close()
	pylab.figure()
	for idx, filter_key in enumerate(combined_filter_keys):
		pylab.subplot(2, 2, idx+1)
		num_samples = 0
		aggregate_data = None
		for key, filtered_pickban in pickbans.items():
			if filter_key in key:
				data = numpy.vstack([pickbans[key][pickban_key] for pickban_key in pickban_order]).transpose()
				num_samples += data.shape[0]
				if aggregate_data is None:
					aggregate_data = data
				else:
					aggregate_data = numpy.vstack((aggregate_data, data))
		if aggregate_data is not None and aggregate_data.shape[0] > 1:
			pylab.boxplot(aggregate_data, whis=1000)
		pylab.title('%s - %s (%d)' % (tag, filter_key, num_samples))
		pylab.xticks(range(1, 11), pickban_order, rotation=-90)
		pylab.ylabel('Seconds to pick/ban')
		pylab.ylim(0, 130)
	fname = 'draft_%s_pick_or_side.png' % tag.lower().replace(' ', '_')
	pylab.tight_layout()
	pylab.savefig(fname)
	pylab.close()

# Aggregate data
pylab.figure()
for idx, key in enumerate(filter_keys):
	pylab.subplot(2, 2, idx+1)
	num_samples = 0
	aggregate_data = None
	for tag, pickbans in team_pickbans.items():
		if key in pickbans:
			data = numpy.vstack([pickbans[key][pickban_key] for pickban_key in pickban_order]).transpose()
			num_samples += data.shape[0]
			if aggregate_data is None:
				aggregate_data = data
			else:
				aggregate_data = numpy.vstack((aggregate_data, data))
	if aggregate_data is not None and aggregate_data.shape[0] > 1:
		pylab.boxplot(aggregate_data, whis=1000)
	pylab.title('All teams - %s (%d)' % (key, num_samples))
	pylab.xticks(range(1, 11), pickban_order, rotation=-90)
	pylab.ylabel('Seconds to pick/ban')
	pylab.ylim(0, 130)
fname = 'draft_all_pick_and_side.png'
pylab.tight_layout()
pylab.savefig(fname)
pylab.close()
pylab.figure()
for idx, filter_key in enumerate(combined_filter_keys):
	pylab.subplot(2, 2, idx+1)
	num_samples = 0
	aggregate_data = None
	for tag, pickbans in team_pickbans.items():
		for key, filtered_pickban in pickbans.items():
			if filter_key in key:
				data = numpy.vstack([pickbans[key][pickban_key] for pickban_key in pickban_order]).transpose()
				num_samples += data.shape[0]
				if aggregate_data is None:
					aggregate_data = data
				else:
					aggregate_data = numpy.vstack((aggregate_data, data))
	if aggregate_data is not None and aggregate_data.shape[0] > 1:
		pylab.boxplot(aggregate_data, whis=1000)
	pylab.title('All teams - %s (%d)' % (filter_key, num_samples))
	pylab.xticks(range(1, 11), pickban_order, rotation=-90)
	pylab.ylabel('Seconds to pick/ban')
	pylab.ylim(0, 130)
fname = 'draft_all_pick_or_side.png'
pylab.tight_layout()
pylab.savefig(fname)
pylab.close()

# Total draft time comparison
totals = OrderedDict()
for tag in sorted(team_pickbans.keys()):
	aggregate_data = []
	for key, filtered_pickbans in team_pickbans[tag].items():
		aggregate_data.extend(filtered_pickbans['total'])
	totals[tag] = aggregate_data
pylab.figure()
pylab.boxplot(totals.values(), whis=1000)
pylab.title('Total Draft Times')
pylab.xticks(range(1, len(totals)+1), totals.keys(), rotation=-90)
pylab.ylabel('Seconds')
fname = 'draft_all_total.png'
pylab.tight_layout()
pylab.savefig(fname)
pylab.close()
