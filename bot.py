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
PROMPT = 'A dreamy, empty hallway lit by flickering neon, no people, silent, liminal space'
RAW_FILE = 'raw.png'
OUT_FILE = 'insta.png'
CROP_BOTTOM = 50               # px to chop off bottom watermark
USER_DATA_DIR = 'playwright_user_data'
HEADLESS = os.getenv('HEADLESS', 'true').lower() == 'true'
POST_COUNT = 3                 # max posts per day

# ─── LOAD & CHECK ENV ──────────────────────────────────────────────────────────
USER = os.getenv('INSTAGRAM_USERNAME')
PASS = os.getenv('INSTAGRAM_PASSWORD')
logger.debug('Env INSTAGRAM_USERNAME=%s', 'SET' if USER else 'NOT SET')
logger.debug('Env INSTAGRAM_PASSWORD=%s', 'SET' if PASS else 'NOT SET')
if not USER or not PASS:
    logger.error('Missing Instagram credentials; aborting.')
    raise EnvironmentError('Set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD')

# ─── IMAGE GRAB ────────────────────────────────────────────────────────────────
def grab_image():
    logger.info('Starting grab_image()')
    with sync_playwright() as p:
        logger.debug('Launching browser (headless=%s)', HEADLESS)
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=HEADLESS
        )
        page = ctx.new_page()
        logger.debug('Navigating to Gemini')
        page.goto('https://gemini.google.com/')
        logger.debug('Clicking Image mode button')
        page.get_by_role("button", name="Image").click()
        logger.debug('Waiting for prompt box')
        prompt_box = page.get_by_role("textbox", name="Ask Gemini")
        prompt_box.wait_for(timeout=60_000)
        prompt_box.click()
        logger.debug('Typing prompt: %s', PROMPT)
        prompt_box.type(PROMPT)
        prompt_box.press("Enter")
        logger.debug('Waiting for "Generating image…"')
        page.get_by_text("Generating image…").wait_for(timeout=120_000)
        logger.debug('Locating result <img>')
        img = page.locator("img[src^='blob:']").first
        logger.debug('Screenshotting to %s', RAW_FILE)
        img.screenshot(path=RAW_FILE)
        ctx.close()
    logger.info('Finished grab_image()')

# ─── IMAGE PROCESSING ──────────────────────────────────────────────────────────
def prep_image():
    logger.info('Starting prep_image()')
    img = Image.open(RAW_FILE)
    w, h = img.size
    logger.debug('Original size: %dx%d', w, h)
    logger.debug('Cropping bottom %d px', CROP_BOTTOM)
    img = img.crop((0, 0, w, h - CROP_BOTTOM))
    side = min(img.size)
    left = (img.width - side) // 2
    top  = (img.height - side) // 2
    logger.debug('Center square crop: side=%d, left=%d, top=%d', side, left, top)
    img = img.crop((left, top, left + side, top + side))
    logger.debug('Resizing to 1080×1080')
    img = img.resize((1080, 1080), Image.LANCZOS)
    img.save(OUT_FILE)
    logger.info('Finished prep_image(); saved %s', OUT_FILE)

# ─── INSTAGRAM POST ────────────────────────────────────────────────────────────
def post_to_instagram():
    logger.info('Starting post_to_instagram()')
    cl = Client()
    logger.debug('Logging in as %s', USER)
    cl.login(USER, PASS)
    logger.debug('Uploading %s', OUT_FILE)
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
    except Exception as e:
        logger.exception('=== do_post() ERROR ===')
    finally:
        logger.info('Leaving do_post()')

# ─── SCHEDULER ─────────────────────────────────────────────────────────────────
def get_random_times(count):
    logger.debug('Generating %d random post times', count)
    times = set()
    while len(times) < count:
        hour = random.randint(6, 22)
        minute = random.randint(0, 59)
        times.add(f"{hour:02d}:{minute:02d}")
    times_list = sorted(times)
    logger.debug('Random times chosen: %s', times_list)
    return times_list

def main_post():
    # immediate test
    logger.info('Running immediate test post')
    do_post()

    # schedule remaining posts
    times = get_random_times(POST_COUNT)
    logger.info('Scheduling up to %d posts at: %s', POST_COUNT, times)
    for t in times:
        schedule.every().day.at(t).do(do_post)

    logger.info('Entering scheduler loop')
    while True:
        schedule.run_pending()
        time.sleep(30)

# ─── ENTRY POINT ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    logger.info('=== Bot starting ===')
    main_post()
    logger.info('=== Bot exiting ===')
