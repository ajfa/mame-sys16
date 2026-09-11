-- Let the machine be shut down from outside, cleanly.
--
-- With no video the emulator has no user interface to quit from, and it does
-- not act on SIGTERM or SIGINT either, so the only way to stop it without
-- killing it is to ask from inside.  When the file work/stop appears, close
-- the machine down properly: that flushes the disk images and closes them,
-- which a kill does not.
local flag = 'work/stop'

emu.register_periodic(function()
	local f = io.open(flag, 'r')
	if f then
		f:close()
		os.remove(flag)
		manager.machine:exit()
	end
end)
