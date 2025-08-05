import os
import random
import time
import schedule
import logging
from instagrapi import Client
from PIL import Image as PILImage
from playwright.sync_api import sync_playwright

# ─── SETUP LOGGING ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ─── CONFIG ────────────────────────────────────────────────────────────────────
PROMPT            = 'A dreamy, empty hallway lit by flickering neon, no people, silent, liminal space'
RAW_FILE          = 'raw.png'
FULL_SCREENSHOT   = 'full_screenshot.png'
OUT_FILE          = 'insta.png'
CROP_BOTTOM       = 50               # px to chop off bottom watermark
USER_DATA_DIR     = 'playwright_user_data'
HEADLESS          = os.getenv('HEADLESS', 'true').lower() == 'true'
POST_COUNT        = 3                # max posts per day
IMAGE_TIMEOUT_MS  = 180_000          # timeout for image to appear (ms)

# ─── LOAD & CHECK ENV ──────────────────────────────────────────────────────────
USER = os.getenv('INSTAGRAM_USERNAME')
PASS = os.getenv('INSTAGRAM_PASSWORD')
if not USER or not PASS:
    logger.error('Missing Instagram credentials; aborting.')
    raise EnvironmentError('Set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD')

# ─── GRAB IMAGE VIA PLAYWRIGHT SCREENSHOT & CROP ───────────────────────────────
def grab_image():
    logger.info('Starting grab_image()')
    with sync_playwright() as p:
        logger.debug('Launching browser (headless=%s)', HEADLESS)
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=HEADLESS
        )
        page = ctx.new_page()

        # Navigate directly into the Gemini image UI
        logger.debug('Navigating to Gemini image UI (/u/1/app)')
        page.goto('https://gemini.google.com/u/1/app', wait_until='networkidle')

        # Kick off generation by typing into the prompt box
        logger.debug('Waiting for prompt input (div[role="textbox"])')
        prompt_box = page.wait_for_selector('div[role="textbox"]', timeout=60_000)
        prompt_box.click()
        logger.debug('Typing prompt: %s', PROMPT)
        prompt_box.type(PROMPT)
        prompt_box.press("Enter")

        # Wait for the “Generating image…” indicator
        logger.debug('Waiting for "Generating image…"')
        page.wait_for_selector('text=Generating image…', timeout=120_000)

        # Wait for the blob <img> element to appear & be visible
        logger.debug('Waiting up to %dms for generated <img> element', IMAGE_TIMEOUT_MS)
        img_el = page.wait_for_selector("img[src^='blob:']", timeout=IMAGE_TIMEOUT_MS)
        img_el.wait_for(state="visible", timeout=IMAGE_TIMEOUT_MS)
        time.sleep(2)  # ensure full render

        # Take full-page screenshot
        logger.debug('Capturing full-page screenshot')
        page.screenshot(path=FULL_SCREENSHOT, full_page=True)

        # Crop exact image region using bounding_box()
        logger.debug('Getting bounding box of image element')
        box = img_el.bounding_box()
        if not box:
            logger.error('Could not determine bounding box for image element')
            raise RuntimeError('Bounding box lookup failed')
        logger.debug('Bounding box: %s', box)

        full = PILImage.open(FULL_SCREENSHOT)
        left, top = int(box["x"]), int(box["y"])
        right = left + int(box["width"])
        bottom = top + int(box["height"])
        logger.debug('Cropping full screenshot to image region: (%d, %d, %d, %d)', left, top, right, bottom)
        region = full.crop((left, top, right, bottom))
        region.save(RAW_FILE)
        logger.info('Saved raw image to %s', RAW_FILE)

        ctx.close()
    logger.info('Finished grab_image()')

# ─── PROCESS IMAGE: CROP WATERMARK & RESIZE ────────────────────────────────────
def prep_image():
    logger.info('Starting prep_image()')
    img = PILImage.open(RAW_FILE)
    w, h = img.size
    logger.debug('Original size: %dx%d', w, h)

    # 1) Chop off bottom watermark
    logger.debug('Cropping bottom %d px', CROP_BOTTOM)
    img = img.crop((0, 0, w, h - CROP_BOTTOM))

    # 2) Center-square crop
    side = min(img.size)
    left = (img.width - side) // 2
    top  = (img.height - side) // 2
    logger.debug('Center-square crop box: (%d, %d, %d, %d)', left, top, left+side, top+side)
    img = img.crop((left, top, left + side, top + side))

    # 3) Resize to Instagram’s 1080×1080
    logger.debug('Resizing to 1080×1080')
    img = img.resize((1080, 1080), PILImage.LANCZOS)
    img.save(OUT_FILE)
    logger.info('Saved processed image to %s', OUT_FILE)

# ─── POST TO INSTAGRAM ─────────────────────────────────────────────────────────
def post_to_instagram():
    logger.info('Starting post_to_instagram()')
    cl = Client()
    logger.debug('Logging in as %s', USER)
    cl.login(USER, PASS)
    logger.debug('Uploading %s', OUT_FILE)
    cl.photo_upload(OUT_FILE, caption='#liminalspace #vaporwave')
    logger.info('Finished post_to_instagram()')

# ─── WORKFLOW ────────────────────────────────────────────────────────────────
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

# ─── SCHEDULING ───────────────────────────────────────────────────────────────
def get_random_times(count):
    times = set()
    while len(times) < count:
        hour = random.randint(6, 22)
        minute = random.randint(0, 59)
        times.add(f"{hour:02d}:{minute:02d}")
    times_list = sorted(times)
    logger.debug('Random post times: %s', times_list)
    return times_list

def main_post():
    logger.info('Immediate test post')
    do_post()

    times = get_random_times(POST_COUNT)
    logger.info('Scheduling posts at: %s', times)
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
