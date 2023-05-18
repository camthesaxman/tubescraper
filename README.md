# Tube Scraper
This is a small Python script which runs a web server that acts as a frontend to YouTube. It is primarily aimed at making YouTube videos accessible on old and low-end devices. For browsers that do not support HTML5 video, this script will serve a Flash version of the video.

## Instructions
1. Install the following dependencies:
   * Python 3
   * yt-dlp Python module - install using `python3 -m pip install yt-dlp`
   * ffmpeg - for Flash support.

2. Run the tubescraper.py script with `python3 tubescraper.py`. The script takes a single parameter specifying the port (which defaults to port 80). Many operating systems require privileged access to port 80, so you may use a different port such as 8080 instead.

3. Access the site from your web browser by typing in the IP or hostname of the device that the script is running on. For example: `http://192.168.1.102`, or `http://localhost`.
