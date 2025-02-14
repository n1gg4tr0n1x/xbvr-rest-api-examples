"""
Given a unmatched funscripts with a filenames that follows SLR naming convenction,
Match them to the scene info scraped from their "proper" site (Badoink etc)
"""

# EDIT BELOW, IF NEEDED.  Do not include a trailing slash.
# -------

XBVR_SERVER_ADDRESS = "http://192.168.1.4:9999"

# -------
# That's all you'll really need to edit


import sys, pathlib
try:
	import requests
except ModuleNotFoundError as e:
	sys.exit("`requests` module required, but not found. You may need to pip install `requests.`")


# Build API URLs based on XBVR server address
FILE_LIST_URL    = XBVR_SERVER_ADDRESS + "/api/files/list"
FILE_MATCH_URL   = XBVR_SERVER_ADDRESS + "/api/files/match"
SCENE_SCRAPE_URL = XBVR_SERVER_ADDRESS + "/api/task/singlescrape" 
SCENE_SEARCH_URL = XBVR_SERVER_ADDRESS + "/api/scene/search"
SCENE_LIST_URL = XBVR_SERVER_ADDRESS + "/api/scene/list"
SCENE_ALTERNATES_URL = XBVR_SERVER_ADDRESS + "/api/scene/alternate_source"
SCENE_DELETE_URL = XBVR_SERVER_ADDRESS + "/api/scene/delete"


def get_scene_id_from_filename(filename:str) -> str:
	"""
	Extract the SLR scene ID number from the funscript's filename
	Returns `str` formatted as "slr-####"
	"""

	components = pathlib.Path(filename).stem.split(".")

	# The SLR-### numeric ID is third from the last group dot-separated values in the base name
	if not components[-3].isnumeric():
		raise ValueError(f"Filename is incorrect format")
	
	return f"slr-{components[-3]}"

def match_funscript_to_scene(funscript:dict, scene:dict):
	"""Instruct XBVR to Match a funscript to a scene, given the XBVR info for both"""

	file_id = funscript["id"]
	scene_id = scene["scene_id"]

	resp = requests.post(FILE_MATCH_URL, json={"file_id":file_id, "scene_id":scene_id})
	
	if not resp.status_code == 200:
		raise Exception(resp.content.decode())

def get_slr_listings_for_site(site_name:str) -> list[dict]:

	data = {
		"dlState":"any",
		"cardSize":"1",
		"lists":[],
		"isHidden":False,
		"releaseMonth":"",
		"cast":[],
		"sites":[site_name],
		"tags":[],
		"cuepoint":[],
		"attributes":["Available from Alternate Sites"],
		"sort":"release_desc",
		"limit":-1,
		"offset":0
	}

	resp = requests.post(SCENE_LIST_URL, json=data)

	if not resp.status_code == 200:
		raise Exception(str(resp.content.decode()))
	
	return resp.json()["scenes"]

def get_alternate_source_for_scene(scene_info:dict):
	"""Look up alternate site info for thing"""

	resp = requests.get(SCENE_ALTERNATES_URL + "/" + str(scene_info["id"]))

	if not resp.status_code == 200:
		raise Exception(str(resp.content.decode()))

	return resp.json()


def delete_scene(scene_info):

	data = {"scene_id": scene_info["id"]}
	resp = requests.post(SCENE_DELETE_URL, json=data)

	if not resp.status_code == 200:
		raise Exception(str(resp.content.decode()))


def get_scenes_for_id(scene_id:str) -> list[dict]:
	"""
	Request known scene data from the XBVR API for a given scene ID
	Returns a list of XBVR info dicts for found scenes
	"""

	resp = requests.get(SCENE_SEARCH_URL, params={"q":f"+id:\"{scene_id}\""})

	if not resp.status_code == 200:
		raise Exception(str(resp.content.decode()))
	
	if resp.json()["results"] == 0:
		return []
	
	return resp.json()["scenes"]

def scrape_slr_scene_id(scene_id:str):
	"""Instruct XBVR to scrape SLR for a given scene ID"""

	if scene_id.lower().startswith("slr-"):
		scene_id = scene_id[4:]

	resp = requests.post(SCENE_SCRAPE_URL, json={
		"site": "slr-single_scene",
		"sceneurl": "https://www.sexlikereal.com/" + scene_id,
		"additional_info" : []
	})

	if not resp.status_code == 200:
		raise Exception(str(resp.content.decode()))

def get_unmatched_files_list() -> list[dict]:
	"""
	Request a list of unmatched files from the XBVR API
	Returns a list of XBVR file info dicts
	"""

	resp = requests.post(FILE_LIST_URL, json={
		"sort":"created_time_desc",
		"state":"unmatched",
		"createdDate":[],
		"resolutions":[],
		"framerates":[],
		"bitrates":[],
		"filename":""
	})

	if not resp.status_code == 200:
		raise Exception(resp.content.decode())

	return resp.json()

def build_alts_list_for_site(site_name:str):

	alt_lookup = {}

	for scene_info in get_slr_listings_for_site(site_name):
		alts = get_alternate_source_for_scene(scene_info)
		
		for alt_site_info in alts:
			slr_id = alt_site_info['external_id']
	
			if slr_id in alts:
				raise Exception("Odd thing")
			
			alt_lookup[slr_id] = scene_info
	
	return alt_lookup


if __name__ == "__main__":
	"""Script starts here"""

	# Request unmatched files list from XBVR
	print("Asking XBVR for unmatched files list...")
	try:
		unmatched_files_info = get_unmatched_files_list()
	except Exception as e:
		sys.exit(f"Error getting unmatched files from XBVR: {e}")
	
	# If no unmatched files found, we're done
	if not unmatched_files_info:
		sys.exit("Nothing to do: No unmatched files found in XBVR.")
	
	print(f"XBVR has {len(unmatched_files_info)} unmatched files.  Let's see here...")

	site_name = sys.argv[1]

	print(f"Building list of alternate sites for {site_name}...")
	alt_scenes_info = build_alts_list_for_site(site_name)

	if not alt_scenes_info:
		sys.exit(f"No alternate scenes found for {site_name}.  Uh-buhbye.")


	# Loop through each unmatched file
	for funscript_info in unmatched_files_info:

		funscript_filename = pathlib.Path(funscript_info["filename"])
		
		# Skip files that aren't `.funscript`s
		if funscript_filename.suffix.lower() != ".funscript":
			print(f"Skipping {funscript_filename}: Not a funscript", file=sys.stderr)
			continue
		
		# Try to extract SLR scene ID from the filename
		try:
			scene_id = get_scene_id_from_filename(funscript_filename.name)
		except Exception as e:
			print(f"Skipping {funscript_filename}: {e} (Probably does not follow the expected file naming convention)", file=sys.stderr)
			continue

		print(f"Found funscript {funscript_filename.name} for SLR ID {scene_id}")

		if scene_id not in alt_scenes_info:
			print("\tNot found in alternate scenes.  Skipping.")
			continue
		
		alt_scene_info = alt_scenes_info[scene_id]
		print(f"\tFound alt: {alt_scene_info['title']}")
		print("\tMatching...", end="")

		try:
			match_funscript_to_scene(funscript_info, alt_scene_info)
		except Exception as e:
			print(f"Nope: {e}")
			continue
		print("Done!")


