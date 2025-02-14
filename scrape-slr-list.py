"""
Given a text file with one SLR ID per line, scrape SLR for those IDs
"""

import sys
import requests

SCRAPER_API_URL = "http://192.168.1.100:9999//api/task/singlescrape"

def get_slr_post_data(scene_id:int) -> dict:
	return {
		"site": "slr-single_scene",
		"sceneurl": "https://www.sexlikereal.com/" + str(scene_id),
		"additional_info" : []
	}

def scrape_slr(post_data:dict):
	return requests.post(SCRAPER_API_URL, json=post_data)


if __name__ == "__main__":

	with open(sys.argv[1]) as scene_ids:
		for scene_id in scene_ids:
			print(str(int(scene_id)) + ":\t" + str(scrape_slr(get_slr_post_data(int(scene_id)))))
			#exit()
	
