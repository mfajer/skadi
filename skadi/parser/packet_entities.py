import bitstring

UF_LeavePVS = 1
UF_Delete = 2
UF_EnterPVS = 4
MAX_ENTITIES = 0x3FFF
MAX_EDICTS = 0x800

class PacketEntitiesParser(object):
	def __init__(self, pbmsg, demo_state):
		self._pbmsg = pbmsg
		self._stream = bitstring.BitStream(bytes=pbmsg.entity_data)
		self._entity_id = -1
		self._state = demo_state

	def _get_bits(self, num):
		'''Get num bits from a BitStream according to the edith algorithm.
		'''
		position = self._stream.pos
		# Find the unsigned little-endian integer in which these bits start
		self._stream.pos = 32 * (position / 32)
		a = self._stream.read('uintle:32')
		# Find the unsigned little-endian integer in which these bits finish
		self._stream.pos = 32 * ((position + num - 1) / 32)
		b = self._stream.read('uintle:32')

		# Compute the bit offset from the start of the a uintle
		read = position & 31

		# This feels like black magic... we shift the starting uintle right
		# losing N bits from the end
		a = a >> read
		# Then we left-shift the finishing uintle and remove the first N bits
		b = b << 32 - read
		# Finally we do a bitwise OR to construct a new uintle
		ab = (a | b)

		# We also prepare a mask to grab the least significant digits from this
		# new uintle and return the masked unintle with a bitwise AND
		mask = (1L << num)-1
		ret = ab & mask

		# And we move the stream forward num bits
		self._stream.pos = position + num
		return ret

	def read_entity_header(self):
		'''Read an entity's header from the BitStream, returning the new entity_id and update_flags. 
		'''
		value = self._get_bits(6)

		# Some special case?
		if (bitstring.BitArray(uintle=value, length=8) & bitstring.BitArray('0x30')).uintle:
			a = (value >> 4) & 3
			b = 16 if (a == 3L) else 0
			value = self._get_bits(4 * a + b) << 4 | (value & 0xF)
			# Need to check the results against edith
			raise NotImplementedError

		update_flags = 0

		if not self._get_bits(1):
			if self._get_bits(1):
				update_flags = update_flags | UF_EnterPVS
		else:
			update_flags = update_flags | UF_LeavePVS
			if self._get_bits(1):
				update_flags = update_flags | UF_Delete

		self._entity_id += value + 1
		return update_flags

	def read_entity_update(self):
		assert entity_id < MAX_ENTITIES, "Entity id is too large"

		raise NotImplementedError

		# Get the entity

		# Update the entity	

	def read_entity_enter_pvs(self):
		'''Initialize a new entity.
		'''
		# Grab the class_idx, the idx into the recv_table
		class_idx = self._get_bits(self._state.class_bits)
		# Edith does not use this quantity, so no idea what it actually is
		serial = self._get_bits(10)

		# Check that we are still within the MAX_EDICTS constraint
		assert self._entity_id < MAX_EDICTS, "Entity %d exceeds max edicts." % self._entity_id








		raise NotImplementedError

	def parse(self):
		'''Parse the data from a CSVCMsg_PacketEntities message.
		'''

		found = 0

		while found < self._pbmsg.updated_entries:
			update_type = self.read_entity_header()

			# Entity enters the PVS and needs to be created
			if update_type & UF_EnterPVS:
				self.read_entity_enter_pvs()
			# Entity leaves the PVS
			elif update_type & UF_LeavePVS:
				assert entities.is_delta, "Leaving PVS on a full update"

				if update_type & UF_Delete:
					raise NotImplementedError
			# Entity just needs updating
			else:
				self.read_entity_update()

			found += 1

		# Not sure what edith is doing here
		if self._pbmsg.is_delta:
			raise NotImplementedError

# Debuging
if __name__ == "__main__":
	from skadi.state import state
	demo_state = state.State(dem)
	parser = PacketEntitiesParser(_pbmsg, demo_state)
	parser.parse()
