import bitstring

UF_LeavePVS = 1
UF_Delete = 2
UF_EnterPVS = 4
MAX_ENTITIES = 16383

def get_bits(stream, num):
	'''Get num bits from a BitStream according to the edith algorithm.
	'''
	position = stream.pos
	# Find the unsigned little-endian integer in which these bits start
	stream.pos = 32 * (position / 32)
	a = bitstring.BitArray(uintle=stream.read('uintle:32'), length=32)
	# Find the unsigned little-endian integer in which these bits finish
	stream.pos = 32 * ((position + num - 1) / 32)
	b = bitstring.BitArray(uintle=stream.read('uintle:32'), length=32)

	# Compute the bit offset from the start of the a uintle
	read = position & 31

	# This feels like black magic... we shift the starting uintle right
	# losing N bits from the end
	a >>= read
	# Then we left-shift the finishing uintle and remove the first N bits
	b <<= 32 - read
	# Finally we do a bitwise OR to construct a new uintle
	ab = (a | b)

	# We also prepare a mask to grab the least significant digits from this
	# new uintle and return the masked unintle with a bitwise AND
	mask = bitstring.BitArray(uintle=(1 << num)-1, length=32)
	ret = ab & mask

	# And we move the stream forward num bits
	stream.pos = position + num
	return ret.uintle

def read_entity_header(prev_entity_id, stream):
	'''Read an entity's header from the BitStream, returning the new entity_id and update_flags. 
	'''
	value = get_bits(stream, 6)

	# Some special case?
	if (bitstring.BitArray(uintle=value, length=8) & bitstring.BitArray('0x30')).uintle:
		raise NotImplementedError
		a = (bitstring.BitArray(uintle=value, length=32) >> 4) & 3

	update_flags = 0

	if not get_bits(stream, 1):
		if get_bits(stream, 1):
			update_flags = update_flags | UF_EnterPVS
	else:
		update_flags = update_flags | UF_LeavePVS
		if get_bits(stream, 1):
			update_flags = update_flags | UF_Delete

	return prev_entity_id + value + 1, update_flags

def read_entity_update(entity_id, stream):
	assert entity_id < MAX_ENTITIES, "Entity id is too large"

	raise NotImplementedError

	# Get the entity

	# Update the entity	

def read_entity_enter_pvs(entity_id, stream):
	'''Initialize a new entity.
	'''
	raise NotImplementedError

def dump_SVC_PacketEntities(entities):
	'''Parse the data from a CSVCMsg_PacketEntities message.
	'''
	stream = bitstring.BitStream(bytes=entities.entity_data)

	entity_id = -1
	found = 0

	while found < entities.updated_entries:
		entity_id, update_type = read_entity_header(entity_id, stream)

		# Entity enters the PVS and needs to be created
		if update_type & UF_EnterPVS:
			read_entity_enter_pvs(entity_id, stream)
		# Entity leaves the PVS
		elif update_type & UF_LeavePVS:
			assert entities.is_delta, "Leaving PVS on a full update"

			if update_type & UF_Delete:
				raise NotImplementedError
		# Entity just needs updating
		else:
			read_entity_update(entity_id, stream)

		found += 1

	# Not sure what edith is doing here
	if entities.is_delta:
		raise NotImplementedError

# Debuging
if __name__ == "__main__":
	dump_SVC_PacketEntities(_pbmsg)
