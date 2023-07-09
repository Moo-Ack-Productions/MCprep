import bpy

# Driver functions for the MCprep sky
def mcprep_sun_ease(world_time):
	x = world_time % 24
	f_x = (-0.073)*(x**2)+(1.762)*(x)-(5.161)
	
	# We want to only return this value if it's above 2, otherwise ignore it
	return f_x if f_x >= 2 else 0

def mcprep_moon_ease(world_time):
	x = world_time % 24
	if x >= 18 and x <= 23.999:
		return (-0.014)*(x**2)+(0.831)*(x)-(10.166)
	else:
		return (-0.012)*(x**2)-(0.164)*(x)+(1.590)

bpy.app.driver_namespace['mcprep_sun_ease'] = mcprep_sun_ease
bpy.app.driver_namespace['mcprep_moon_ease'] = mcprep_moon_ease
