import os
import random
import time
import schedule
import logging
from instagrapi import Client
from PIL import Image
from playwright.sync_api import sync_playwright

# ─── SETUP LOGGING ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ─── CONFIG ────────────────────────────────────────────────────────────────────
PROMPT        = 'A dreamy, empty hallway lit by flickering neon, no people, silent, liminal space'
RAW_FILE      = 'raw.png'
OUT_FILE      = 'insta.png'
CROP_BOTTOM   = 50               # px to chop off bottom watermark
USER_DATA_DIR = 'playwright_user_data'
HEADLESS      = os.getenv('HEADLESS', 'true').lower() == 'true'
POST_COUNT    = 3                # max posts per day
IMAGE_TIMEOUT = 180_000          # wait up to 180s for image

# ─── LOAD & CHECK ENV ──────────────────────────────────────────────────────────
USER = os.getenv('INSTAGRAM_USERNAME')
PASS = os.getenv('INSTAGRAM_PASSWORD')
if not USER or not PASS:
    logger.error('Missing Instagram credentials; aborting.')
    raise EnvironmentError('Set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD')

# ─── IMAGE GRAB VIA SCREENSHOT ─────────────────────────────────────────────────
def grab_image():
    logger.info('Starting grab_image()')
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=HEADLESS
        )
        page = ctx.new_page()

        logger.debug('Navigating to Gemini image UI (/u/1/app)')
        page.goto('https://gemini.google.com/u/1/app')

        # wait for the labelled prompt box ("Ask Gemini")
        logger.debug('Waiting for "Ask Gemini" prompt box')
        prompt_box = page.get_by_role("textbox", name="Ask Gemini")
        prompt_box.wait_for(timeout=60_000)
        prompt_box.click()

        logger.debug('Typing prompt: %s', PROMPT)
        prompt_box.type(PROMPT)
        prompt_box.press("Enter")

        # wait for “Generating image…” then the blob img
        logger.debug('Waiting for "Generating image…"')
        page.get_by_text("Generating image…").wait_for(timeout=120_000)

        logger.debug('Waiting up to %dms for image element', IMAGE_TIMEOUT)
        img_el = page.wait_for_selector("img[src^='blob:']", timeout=IMAGE_TIMEOUT)
        img_el.wait_for(state="visible", timeout=IMAGE_TIMEOUT)
        time.sleep(3)  # ensure full render

        logger.debug('Screenshotting image element to %s', RAW_FILE)
        img_el.screenshot(path=RAW_FILE)

        ctx.close()
    logger.info('Finished grab_image()')

# ─── IMAGE PROCESSING ──────────────────────────────────────────────────────────
def prep_image():
    logger.info('Starting prep_image()')
    img = Image.open(RAW_FILE)
    w, h = img.size
    logger.debug('Original image size: %dx%d', w, h)

    # crop off watermark strip
    img = img.crop((0, 0, w, h - CROP_BOTTOM))

    # center-square crop
    side = min(img.size)
    left = (img.width - side) // 2
    top  = (img.height - side) // 2
    img = img.crop((left, top, left + side, top + side))

    # resize to 1080×1080
    img = img.resize((1080, 1080), Image.LANCZOS)
    img.save(OUT_FILE)
    logger.info('Saved processed image to %s', OUT_FILE)

# ─── INSTAGRAM POST ────────────────────────────────────────────────────────────
def post_to_instagram():
    logger.info('Starting post_to_instagram()')
    cl = Client()
    cl.login(USER, PASS)
    cl.photo_upload(OUT_FILE, caption='#liminalspace #vaporwave')
    logger.info('Finished post_to_instagram()')

# ─── POST WORKFLOW ─────────────────────────────────────────────────────────────
def do_post():
    logger.info('=== do_post() BEGIN ===')
    try:
        grab_image()
        prep_image()
        post_to_instagram()
        logger.info('=== do_post() SUCCESS ===')
    except Exception:
        logger.exception('=== do_post() ERROR ===')
    finally:
        logger.info('Leaving do_post()')

# ─── SCHEDULER ─────────────────────────────────────────────────────────────────
def get_random_times(count):
    times = set()
    while len(times) < count:
        hour = random.randint(6, 22)
        minute = random.randint(0, 59)
        times.add(f"{hour:02d}:{minute:02d}")
    return sorted(times)

def main_post():
    logger.info('Immediate test post')
    do_post()

    times = get_random_times(POST_COUNT)
    logger.info('Scheduling posts at: %s', times)
    for t in times:
        schedule.every().day.at(t).do(do_post)

    logger.info('Scheduler loop start')
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == '__main__':
    logging.info('Bot starting')
    main_post()
    logging.info('Bot exiting')
