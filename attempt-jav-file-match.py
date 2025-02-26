#!/usr/bin/env python3

"""
This script will look through all your unmatched files in XBVR for potential JAV files.
For all potential unmatched JAV content, it will try to determine if the scene has been 
scraped by XBVR yet, and match it to the scene if it has.

If the scene has not yet been added to XBVR, it will iterate through the known JAV 
scrapers in an attempt to scrape the scene, then match the files once the scene has 
been successfully scraped.

This script works best if the only unmatched files you have in XBVR are JAV files.  I'm 
not aware of a reliable method of determining that a file is FOR SURE a JAV scene based 
on file name alone, so it tends to pick up a lot of files that aren't JAV.  This is 
relatively harmless, but just wastes time while it tries to scrape all the JAV scrapers 
for scenes that aren't JAV and definitely aren't in the JAV scraper databases.
"""

# Edit the below configuration based on your environment
# -------

XBVR_SERVER_ADDRESS:str = "http://localhost:9999"
"""
Base address:port at which your XBVR server can be accessed
"""

JAV_SCRAPE_TIMEOUT:int = 12
"""
Time, in seconds, to wait while scraping and potentially indexing a scene from a JAV Scraper

This is needed because the XBVR API does not return status or success info after initiating 
a JAV Database scrape, so we goin' in blind here.  Adjust this depending on how long it 
typically takes your setup to fully scrape and index a scene.  For me, 12 seconds is good.
"""

# -------
# That's probably all you'll really need to edit


import sys, re, time, enum, dataclasses
try:
	import requests
except ModuleNotFoundError as e:
	sys.exit("`requests` module required, but not found. You may need to pip install `requests.`")


# Build API URLs based on XBVR server address
FILE_LIST_URL        = XBVR_SERVER_ADDRESS + "/api/files/list"
FILE_MATCH_URL       = XBVR_SERVER_ADDRESS + "/api/files/match"
SCENE_SCRAPE_JAV_URL = XBVR_SERVER_ADDRESS + "/api/task/scrape-javr"
SCENE_SEARCH_URL     = XBVR_SERVER_ADDRESS + "/api/scene/search"

CLEAN_FILENAME = re.compile(r"[^a-z0-9]+")
"""Use with re.sub to replace extraneous characters with a single space"""

PAT_JAV_ID = re.compile(r"(?<![a-z])([a-z]{4,6})\s*[\-_\.]*\s*([0-9]{3,6})", re.I)
"""Regex pattern to find potential JAV IDs -- this is pretty loose and tends to produce (relatively harmless) false positives"""

class JavScrapers(enum.StrEnum):
	"""Available JAV scrapers"""

	JAVDATABASE = "javdatabase"
	"""javdatabase.com"""

	R18DEV = "r18d"
	"""r18.dev"""
	
	JAVLIBRARY = "javlibrary"
	"""javlibrary.com"""

	#JAVLAND = "javland"
	#"""jav.land -- Currently deactivated because it times out"""

@dataclasses.dataclass
class JavId:
	"""Represents a JAV ID in various forms"""

	studio_code:str
	"""The studio that produced the scene"""

	scene_code:str
	"""The number of the scene"""

	def __post_init__(self):
		"""Post processing"""

		self.studio_code = self.studio_code.strip().upper()
		self.scene_code  = self.scene_code.strip().lstrip("0").zfill(3)

		# "DSVR" should really be "3DSVR"
		if self.studio_code == "DSVR":
			self.studio_code = "3DSVR"

	def as_content_id(self) -> str:
		"""JAV ID in FANZA Content ID Format"""

		if self.studio_code == "3DSVR":
			studio_code = "13DSVR"
		else:
			studio_code = self.studio_code
			
		return studio_code.upper() + self.scene_code.upper().lstrip("0").zfill(5)
	
	def as_dvd_id(self) -> str:
		"""JAV ID in DVD ID format"""

		if self.studio_code == "3DSVR":
			scene_code = self.scene_code.upper().lstrip("0").zfill(4)
		else:
			scene_code = self.scene_code.upper().lstrip("0").zfill(3)

		return self.studio_code.upper() + "-" + scene_code
	
	def id_formats(self) -> list:
		"""A list of all available ID formats"""
		return [self.as_content_id(), self.as_dvd_id()]
	
	@classmethod
	def from_string(cls, jav_id:str):
		"""Create a `JavId` from a string"""

		match = PAT_JAV_ID.search(jav_id)
		if not match:
			raise ValueError("Invalid JAV ID: " + str(jav_id))
		
		return cls(
			studio_code = match.group(1).upper(),
			scene_code  = match.group(2).lstrip("0")
		)
	
	def __str__(self):
		return self.as_dvd_id()
	
	def __hash__(self):
		return hash(str(self))


requests_session = requests.Session()

def get_unmatched_files_list() -> list[dict]:
	"""
	Request a list of unmatched files from the XBVR API
	Returns a list of XBVR file info dicts
	"""

	global requests_session

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

def get_scenes_for_id(scene_id:str) -> list[dict]:
	"""
	Request known scene data from the XBVR API for a given scene ID
	Returns a list of XBVR info dicts for found scenes
	"""

	global requests_session

	resp = requests_session.get(SCENE_SEARCH_URL, params={"q":f"+id:\"{scene_id}\""})

	if not resp.status_code == 200:
		raise Exception(str(resp.content.decode()))
	
	if resp.json()["results"] == 0:
		return []
	
	return resp.json()["scenes"]

def scrape_jav_scene(jav_id:JavId, scraper:JavScrapers=JavScrapers.JAVDATABASE):
	"""
	Scrape a JAV scene given an ID (ex PXVR-001) and a JAV Database Scraper
	"""

	global requests_session

	scrape_id = jav_id.as_content_id() if scraper is JavScrapers.R18DEV else jav_id.as_dvd_id()

	resp = requests_session.post(SCENE_SCRAPE_JAV_URL, json={
		"q": scrape_id,
		"s": str(scraper)
	})

	if not resp.status_code == 200:
		raise Exception(resp.content.decode())
	
	# Not my favorite, but we dont' know when the scrape request
	# will complete.  So... wait...
	time.sleep(10)

def match_file_to_scene(file_info:dict, scene_info:dict):
	"""Instruct XBVR to Match a file to a scene, given the XBVR info for both"""

	global requests_session

	file_id = file_info["id"]
	scene_id = scene_info["scene_id"]

	resp = requests_session.post(FILE_MATCH_URL, json={"file_id":file_id, "scene_id":scene_id})
	
	if not resp.status_code == 200:
		raise Exception(resp.content.decode())
	
def filter_unmatched_files_by_jav_id(unmatched_files_info:list[dict]) -> dict[JavId, list[dict]]:
	"""
	Given a list of fileinfo dicts, group files by their JAV ID
	Returns a dict of `JavId`s and a list of their associated fileinfo dicts
	"""

	unmatched_by_jav_id:dict[JavId,list[dict]] = {}

	# First, collect all unmatched JAV files and group them by their ID
	for f in unmatched_files_info:
		
		try:
			jav_id = JavId.from_string(f["filename"])
		except ValueError as e:
			# JAV ID not found in filename
			continue

		# TODO: Add more false positive checks
		if jav_id.studio_code.lower().startswith("czech"):
			# Skip czechvr false positives
			continue
		
		if jav_id not in unmatched_by_jav_id:
			# Add empty JAV ID entry if not already there
			#print(jav_id)
			unmatched_by_jav_id[jav_id] = []
		
		unmatched_by_jav_id[jav_id].append(f)
	
	return unmatched_by_jav_id

def get_scene_for_jav_id(jav_id:JavId, potential_scenes:list[dict]) -> dict|None:
	"""
	Given a JAV ID and potential scenes, return a scene if it matches the JAV ID
	
	Returns a scene info dict or None
	"""

	for scene_info in potential_scenes:

		try:
			scene_id = JavId.from_string(scene_info["scene_id"])
			#print(f"Scene has {scene_id}")
		except ValueError:
			#print(f"Nooo...", scene_info["scene_id"])
			return None

		if scene_id == jav_id:
			return scene_info
	
	return None


if __name__ == "__main__":

	count_good = 0
	count_bad  = 0

	print("Getting unmatched JAV videos from XBVR...")
	try:
		unmatched_files_info = get_unmatched_files_list()
	except Exception as e:
		print(f"Failed to get a list of unmatched files from XBVR: {e}", file=sys.stderr)
		print("Please ensure the configuration is correct near the top of the file.", file=sys.stderr)
		sys.exit(1)

	unmatched_by_jav_id = filter_unmatched_files_by_jav_id(unmatched_files_info)

	print(f"Found {len(unmatched_by_jav_id)} JAV Scene IDs ({sum(len(f) for f in unmatched_by_jav_id.values())} files) that are currently unmatched.")

	# For each JAV ID, determine if the scene exists or needs to be scraped
	# Match the files accordingly
	for jav_id, file_infos in unmatched_by_jav_id.items():

		print("")
		print(f"Searching for {jav_id} ({len(unmatched_by_jav_id[jav_id])} files)...")
		
		potential_scenes = []
		for jid in jav_id.id_formats():
			potential_scenes.extend(get_scenes_for_id(jid))
		jav_scene_info   = get_scene_for_jav_id(jav_id, potential_scenes)

		jav_scrapers = iter(JavScrapers)

		while not jav_scene_info:
			try:
				jav_scraper = next(jav_scrapers)
			except StopIteration:
				break

			print(f"  🔍 Attempting to scrape {jav_scraper}...")
			scrape_jav_scene(jav_id, jav_scraper)

			potential_scenes = []
			for jid in jav_id.id_formats():
				potential_scenes.extend(get_scenes_for_id(jid))
				jav_scene_info   = get_scene_for_jav_id(jav_id, potential_scenes)
		
		if not jav_scene_info:
			print("  ❌ Ultimately not found in scenes or external sources")
			count_bad += 1
			continue
		
		print("  ✅ Found!  Matching files to scene: " + jav_scene_info["scene_id"] + ": " + jav_scene_info["title"][:30] + "...")
		for file_info in file_infos:
			match_file_to_scene(file_info, jav_scene_info)
		count_good += 1
	
	print("")
	print(f"Complete.  ✅ Scenes Matched: {count_good}, ❌ Scenes Not Matched: {count_bad}")
