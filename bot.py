import os
import random
import time
import schedule
from instagrapi import Client
from PIL import Image
from playwright.sync_api import sync_playwright

# ─── CONFIG ────────────────────────────────────────────────────────────────────
PROMPT = 'A dreamy, empty hallway lit by flickering neon, no people, silent, liminal space'
RAW_FILE = 'raw.png'
OUT_FILE = 'insta.png'
CROP_BOTTOM = 50  # pixels to chop off bottom (watermark)
USER_DATA_DIR = 'playwright_user_data'
HEADLESS = os.getenv('HEADLESS', 'true').lower() == 'true'
POST_COUNT = 3     # number of posts per day

# load Instagram creds
USER = os.getenv('INSTAGRAM_USERNAME')
PASS = os.getenv('INSTAGRAM_PASSWORD')
if not USER or not PASS:
    raise EnvironmentError('Set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD in your env')

def grab_image():
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=HEADLESS
        )
        page = ctx.new_page()
        page.goto('https://gemini.google.com/')
        # click the "Image" button
        page.get_by_role("button", name="Image").click()
        # wait for prompt box
        prompt_box = page.get_by_role("textbox", name="Ask Gemini")
        prompt_box.wait_for(timeout=60_000)
        prompt_box.click()
        prompt_box.type(PROMPT)
        prompt_box.press("Enter")
        # wait for generation
        page.get_by_text("Generating image…").wait_for(timeout=120_000)
        # screenshot the result image
        img = page.locator("img[src^='blob:']").first
        img.screenshot(path=RAW_FILE)
        ctx.close()

def prep_image():
    img = Image.open(RAW_FILE)
    w, h = img.size
    img = img.crop((0, 0, w, h - CROP_BOTTOM))
    side = min(img.size)
    left = (img.width - side) // 2
    top  = (img.height - side) // 2
    img = img.crop((left, top, left + side, top + side))
    img = img.resize((1080, 1080), Image.LANCZOS)
    img.save(OUT_FILE)

def post_to_instagram():
    cl = Client()
    cl.login(USER, PASS)
    cl.photo_upload(OUT_FILE, caption='#liminalspace #vaporwave')

def do_post():
    print(f"Posting at {time.strftime('%H:%M:%S')}")
    grab_image()
    prep_image()
    post_to_instagram()
    print("✅ Posted.")

def get_random_times(count):
    times = set()
    while len(times) < count:
        hour = random.randint(6, 22)      # between 06:00 and 22:59
        minute = random.randint(0, 59)
        times.add(f"{hour:02d}:{minute:02d}")
    return sorted(times)

if __name__ == '__main__':
    # 1) Immediate test post
    print("Starting test post...")
    do_post()

    # 2) Schedule up to POST_COUNT posts at random times today
    times = get_random_times(POST_COUNT)
    print("Scheduling posts at:", ', '.join(times))
    for t in times:
        schedule.every().day.at(t).do(do_post)

    # 3) Run scheduler loop
    print("Entering schedule loop...")
    while True:
        schedule.run_pending()
        time.sleep(30)
