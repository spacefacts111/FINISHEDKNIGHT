import os
import random
import datetime
import time
import schedule
from instagrapi import Client
from PIL import Image
from playwright.sync_api import sync_playwright

# --- Configuration ---
PROMPT = 'A dreamy, empty hallway lit by flickering neon, no people, silent, liminal space'
RAW = 'raw.png'
OUT = 'insta.png'
CROP_H = 50
USER_DATA = 'playwright_user_data'
POST_COUNT = 3  # number of scheduled posts per day

# Load Instagram creds
IU = os.getenv('INSTAGRAM_USERNAME')
PWD = os.getenv('INSTAGRAM_PASSWORD')
if not IU or not PWD:
    raise EnvironmentError('Set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD')

# 1) Browser-automate Gemini to grab image
def grab_image():
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA,
            headless=os.getenv('HEADLESS', 'true') == 'true'
        )
        page = ctx.new_page()
        page.goto('https://gemini.google.com/')
        page.click('button:has-text("Image")')
        page.click('div[role="textbox"]')
        page.keyboard.type(PROMPT)
        page.keyboard.press('Enter')
        page.wait_for_selector('text="Generating image..."', timeout=120_000)
        img = page.wait_for_selector('img[src^="blob:"]', timeout=120_000)
        img.screenshot(path=RAW)
        ctx.close()

# 2) Crop watermark & resize
def prep_image():
    img = Image.open(RAW)
    w, h = img.size
    img = img.crop((0, 0, w, h - CROP_H))
    side = min(img.width, img.height)
    left = (img.width - side) // 2
    top = (img.height - side) // 2
    img = img.crop((left, top, left + side, top + side))
    img = img.resize((1080, 1080), Image.LANCZOS)
    img.save(OUT)

# 3) Upload to Instagram
def post():
    cl = Client()
    cl.login(IU, PWD)
    cl.photo_upload(OUT, caption='#liminalspace #vaporwave')
    print(f"Posted to @{IU} at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# Main workflow
def main_post():
    grab_image()
    prep_image()
    post()

if __name__ == '__main__':
    # Immediate test post
    print('Running immediate test post...')
    main_post()

    # Schedule future posts at random times today
    times = []
    for _ in range(POST_COUNT):
        hour = random.randint(0, 23)
        minute = random.randint(0, 59)
        times.append(f"{hour:02d}:{minute:02d}")
    # Remove duplicates and sort
    times = sorted(set(times))[:POST_COUNT]

    for t in times:
        schedule.every().day.at(t).do(main_post)
        print(f"Scheduled post at {t}")

    # Loop forever to run scheduled jobs
    print('Entering scheduler loop...')
    while True:
        schedule.run_pending()
        time.sleep(30)
