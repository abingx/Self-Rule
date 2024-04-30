#crontab -e 
#0 5 * * * /usr/local/bin/python3 /Users/xuebing/wallpaper.py >> /Users/xuebing/wallpaper.log 2>&1
import feedparser
import requests
import re
from urllib.parse import urljoin
# RSS feed URL
rss_url = 'https://basicappleguy.com/basicappleblog?format=rss'
# Parse the RSS feed
feed = feedparser.parse(rss_url)
# Get the latest entry
latest_entry = feed.entries[0]
# Extract the content of the latest entry
content = latest_entry.content[0].value
# Regular expression patterns for matching the URLs
patterns = [
    r'https:\/\/basicappleguy\.com\/s\/([a-zA-Z0-9_]+)_iPad\.(png|heic)',
    r'https:\/\/basicappleguy\.com\/s\/([a-zA-Z0-9_]+)_Mac\.(png|heic)',
    r'https:\/\/basicappleguy\.com\/s\/([a-zA-Z0-9_]+)_iPhone\.(png|heic)'
]
# Function to download an image
def download_image(url, target_directory, filename):
    response = requests.get(url)
    if response.status_code == 200:
        # Ensure the target directory exists
        if not os.path.exists(target_directory):
            os.makedirs(target_directory)
        # Construct the full path for the file
        full_path = os.path.join(target_directory, filename)
        with open(full_path, 'wb') as file:
            file.write(response.content)
        print(f"Downloaded {filename} to {target_directory}")
    else:
        print(f"Failed to download {url}")
# Add the os module to import os.makedirs and os.path
import os
# Specify the target directory
target_directory = "/Users/xuebing/Library/Mobile Documents/iCloud~is~workflow~my~workflows/Documents/wallpaper"
# Iterate over the patterns and download the images
for i, pattern in enumerate(patterns):
    match = re.search(pattern, content)
    if match:
        # Construct the full URL and download the image
        image_url = urljoin(rss_url, match.group(0))
        # Include the target directory in the filename
        filename = f"{target_directory}/{['iPad', 'Mac', 'iPhone'][i]}.png"
        print(f"Downloading {filename} from {image_url}")
        download_image(image_url, target_directory, os.path.basename(filename))  # Pass the base name of the file
    else:
        print(f"No match found for pattern: {pattern}")