import math

class State(object):
	def __init__(self, demo):
		self.class_bits = int(math.ceil(math.log(demo.server_info['max_classes'], 2)))
		self.classes = demo.class_info
		self.recv_tables = demo.recv_tables
