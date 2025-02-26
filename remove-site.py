"""
Remove scraper data for a given site name.
This removes any scenes scraped from the site, and unmatches any files.
"""

# EDIT BELOW, IF NEEDED.  Do not include a trailing slash.
# -------

XBVR_SERVER_ADDRESS = "http://localhost:9999"

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

def get_scenes_for_site(site_name:str) -> list[dict]:

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
		#"attributes":["Available from Alternate Sites"],
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


if __name__ == "__main__":
	"""Script starts here"""

	if len(sys.argv) < 2:
		sys.exit(f"Usage: {__name__} sitename")

	site_name = sys.argv[1]


	print(f"Asking XBVR for scenes from {site_name}...")

	counter = 0

	for idx, scene_info in enumerate(get_scenes_for_site(site_name)):
	#	print(scene_info)
	#	if not scene_info["scene_id"].lower().startswith("slr-"):
	#		continue
		
		print(f"{counter}] Deleting {scene_info['scene_id']}: {scene_info['title']}...", end="")
		try:
			delete_scene(scene_info)
		except Exception as e:
			print(" ** NO **")
		else: print(" Done!")
		counter += 1 
