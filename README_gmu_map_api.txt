GMU Campus Food Delivery Robot — Map Downloader

Description:

This script queries multiple Overpass API servers for OpenStreetMap (OSM) data pertinent to George Mason University's Fairfax campus in Virginia, USA.

It is meant to serve as the primary map data source for the robot's navigation script. The team needs this data to build navigation information, route around known closures and blockages, and calculate alternative routes.

Requirements:

Python 3.12 or later

Python requests library

A stable internet connection

Sufficient disk storage for the active JSON map and historical backups

An IDE such as PyCharm or Visual Studio Code for the documented manual execution method

Installation and Usage:

The script was developed and tested using Python 3.12 in PyCharm on Windows 11.

To run the script manually:

Install Python 3.12 or later.

Install the requests library using python -m pip install requests.

Open gmu_map_api.py in an IDE such as PyCharm.

Ensure the correct Python interpreter is configured and that you are connected to the internet.

Select Run and allow the script to execute until completion.

Review the console output to confirm that the map data was successfully downloaded, validated, and saved.

Output:

The script generates OpenStreetMap data containing pathways, coordinates, and associated tags for ingestion by the Dijkstra algorithm in the robot's navigation system.

This information supports the identification of known closures and blockages and the calculation of alternative routes.

Two JSON files are saved alongside the Python script:

gmu_map.json — The active map used by the navigation system.

gmu_map_YYYYMMDD_HHMMSS.json — A timestamped historical copy of the downloaded map.

Historical backups are excluded from Git through .gitignore. A rolling 30-day retention policy has been proposed and approved but is not yet implemented.

Error Handling:

The script queries multiple Overpass API servers, with up to three rounds of attempts. This is intended to ensure a successful download if one or more servers are experiencing connectivity problems, excessive traffic, or other errors.

Before saving the downloaded data, the script checks that the response contains valid map elements and that pathway geometry is complete.

If a server fails, the script attempts another available server. If the data cannot be retrieved successfully, the script reports the failure.

If an error occurs while saving the files, the script exits rather than repeating the download process.

Automated Scheduling:

The script is intended to execute automatically once every 12 hours using cron on an Ubuntu server.

Automated scheduling is being handled separately by the DevOps team and has not yet been implemented or verified.

Ubuntu deployment and scheduling instructions will be added after the process has been tested.