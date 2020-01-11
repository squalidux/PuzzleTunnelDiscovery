#!/bin/bash

./facade.py tools blender --current_trial 25 condor.u3/claw-rightbv.dt.tcp/ --puzzle_name claw-rightbv.dt.tcp \
	--camera_origin 0 -10 15 \
	--camera_lookat 0 0 0 \
	--camera_up 0 0 1 \
	--light_auto \
	--image_frame 0 \
	--saveas blender/blender_claw.blend \
	--floor_origin 0 0 -0.25 \
	"$@" \
	~/HGSTArchive/blenderout/
