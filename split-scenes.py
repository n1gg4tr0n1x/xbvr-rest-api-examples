"""
Exporting scene data from XBVR can sometimes be too large to import back in.
This splits the JSON files into smaller files that can be imported more easily.
"""

import sys, json, pathlib

SCENES_PER_FILE:int = 5000

if __name__ == "__main__":

	if not len(sys.argv) > 1:
		sys.exit(f"Usage: {__file__} xbvr-content-bundle.js")
	
	source_file = pathlib.Path(sys.argv[1])
	
	with open(source_file) as f:
		f_json = json.load(f)
	
	timestamp = f_json["timestamp"]
	bundleVersion = f_json["bundleVersion"]
	scenes = f_json["scenes"]
	
	count=0
	for i in range(0, len(scenes), SCENES_PER_FILE):

		count += 1

		scenes_sliced = scenes[i:i+SCENES_PER_FILE]

		output = {
			"timestamp": timestamp,
			"bundleVersion": bundleVersion,
			"scenes": scenes_sliced
		}

		output_file = source_file.with_name(source_file.stem + "_" + str(count)).with_suffix(".json")

		with open(output_file,"w") as f:
			print(f"Writing {i} - {i+len(scenes_sliced)} to {output_file}...")
			json.dump(output, f)

	print("Done")