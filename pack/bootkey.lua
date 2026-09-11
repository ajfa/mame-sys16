-- Type the monitor's boot command into the machine's terminal, so it comes
-- up in GENIX without anything having to be typed by hand.
--
-- The ROM stops at its prompt and waits for a key; k is "boot dc(1,0)vmunix".
-- Eight seconds is well past the prompt and well short of anything else
-- happening, and the key goes through the emulated terminal's own keyboard,
-- so the machine sees it exactly as if it had been typed.
local kbd = manager.machine.natkeyboard
local done = false

emu.register_periodic(function()
	if done then return end
	if manager.machine.time.seconds >= 8 then
		done = true
		kbd:post("k\n")
	end
end)
