"""
For each unmatched file in XBVR, search XBVR for scenes that may have it 
as a known filename.  If a scene is found, match the file to the scene.

This is done in a case-insensitive, file-extention-agnostic way, and 
strips filenames of unusual characters which may be inconsistent, to 
improve matches.
"""

XBVR_SERVER_ADDRESS = "http://192.168.1.4:9999"

# -------
# That's all you'll really need to edit


import sys, pathlib, json, concurrent.futures, re
try:
	import requests
except ModuleNotFoundError as e:
	sys.exit("`requests` module required, but not found. You may need to pip install `requests.`")


# Build API URLs based on XBVR server address
FILE_LIST_URL        = XBVR_SERVER_ADDRESS + "/api/files/list"
FILE_MATCH_URL       = XBVR_SERVER_ADDRESS + "/api/files/match"
SCENE_SCRAPE_URL     = XBVR_SERVER_ADDRESS + "/api/task/singlescrape" 
SCENE_SEARCH_URL     = XBVR_SERVER_ADDRESS + "/api/scene/search"
SCENE_LIST_URL       = XBVR_SERVER_ADDRESS + "/api/scene/list"
SCENE_ALTERNATES_URL = XBVR_SERVER_ADDRESS + "/api/scene/alternate_source"
SCENE_DELETE_URL     = XBVR_SERVER_ADDRESS + "/api/scene/delete"

CLEAN_FILENAME = re.compile(r"[^a-z0-9]+")
"""Use with re.sub to replace extraneous characters with a single space"""

requests_session = requests.Session()

def search_scenes(query:str) -> list[dict]:
	"""
	General search ("Quick Search" via web GUI)
	Returns a list of XBVR info dicts for found scenes
	"""

	# Search based on the basename
	try:
		resp = requests_session.get(SCENE_SEARCH_URL, params={"q":query})

		if not resp.status_code == 200:
			raise Exception(str(resp.content.decode()))
		
		if resp.json()["results"] == 0:
			return []
		return resp.json()["scenes"]
	
	except requests.JSONDecodeError as e:
		print(f"**INVALID RESPONSE: {e}", file=sys.stderr)
		return []


def get_known_filenames_for_scene(scene_info:dict) -> list[str]:
	"""
	Given a scene_info dict, return a list of known filenames
	Returns a list of filenames as strings
	"""
	filenames = json.loads(scene_info.get("filenames_arr"))
	return filenames or []


def get_unmatched_files_list() -> list[dict]:
	"""
	Request a list of unmatched files from the XBVR API
	Returns a list of XBVR file info dicts
	"""

	resp = requests_session.post(FILE_LIST_URL, json={
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

def scene_has_known_filename(scene_info:dict, file_info:dict) -> bool:
	"""
	Check if a given file is in the "known filenames" of a given scene
	Returns bool
	"""

	unmatched_filestem = CLEAN_FILENAME.sub(" ", pathlib.Path(file_info["filename"]).stem.lower())
	known_filestems    = [CLEAN_FILENAME.sub(" ", pathlib.Path(p).stem.lower()) for p in get_known_filenames_for_scene(scene_info)]
	#print(unmatched_filestem)

	return unmatched_filestem in known_filestems

def match_file_to_scene(file_info:dict, scene_info:dict):
	"""Instruct XBVR to Match a file to a scene, given the XBVR info for both"""

	file_id = file_info["id"]
	scene_id = scene_info["scene_id"]

	resp = requests_session.post(FILE_MATCH_URL, json={"file_id":file_id, "scene_id":scene_id})
	
	if not resp.status_code == 200:
		raise Exception(resp.content.decode())
	
def find_and_match_scene_for_file(unmatched_file_info:dict) -> dict:
	"""
	Find and match a scene with a file
	Returns a scene info dict of the matched scene (or None)
	"""

	#print("Checking " + unmatched_file_info["filename"])

	potential_scenes = search_scenes(pathlib.Path(unmatched_file_info["filename"]).stem.lower())

	for scene_info in potential_scenes:

		if scene_has_known_filename(scene_info, unmatched_file_info):
			print("Matching: " + scene_info["site"] + ": " + scene_info["title"] + " with " + unmatched_file_info["filename"])
			match_file_to_scene(unmatched_file_info, scene_info)
			return scene_info
	return None
	

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

	#random.shuffle(unmatched_files_info)

	with concurrent.futures.ThreadPoolExecutor() as executor:
		results = list(executor.map(find_and_match_scene_for_file, unmatched_files_info))
	
	matches_count = len([r for r in results if r is not None])

	print(f"{matches_count} file(s) matched.")