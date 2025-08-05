import os
import random
import time
import schedule
import logging
import requests
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

# ─── LOAD & CHECK ENV ──────────────────────────────────────────────────────────
USER = os.getenv('INSTAGRAM_USERNAME')
PASS = os.getenv('INSTAGRAM_PASSWORD')
logger.debug('INSTAGRAM_USERNAME set: %s', bool(USER))
logger.debug('INSTAGRAM_PASSWORD set: %s', bool(PASS))
if not USER or not PASS:
    logger.error('Missing Instagram credentials; aborting.')
    raise EnvironmentError('Set INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD')

# ─── IMAGE GRAB VIA NETWORK INTERCEPT ───────────────────────────────────────────
def grab_image():
    logger.info('Starting grab_image()')
    with sync_playwright() as p:
        logger.debug('Launching browser (headless=%s)', HEADLESS)
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=HEADLESS
        )
        page = ctx.new_page()

        logger.debug('Navigating directly into Image mode')
        page.goto('https://gemini.google.com/?modal=images')

        # 1) Kick off the generation by typing into the prompt box
        logger.debug('Waiting for prompt input')
        prompt_box = page.wait_for_selector('div[role="textbox"]', timeout=60_000)
        prompt_box.click()
        logger.debug('Typing prompt: %s', PROMPT)
        prompt_box.type(PROMPT)
        prompt_box.press("Enter")

        # 2) Intercept the GraphQL response that carries the signed URI
        logger.debug('Waiting for GraphQL response with image URI')
        response = page.wait_for_response(
            lambda r: r.request.method == "POST" and "generateImage" in r.url,
            timeout=120_000
        )
        data = response.json()
        signed_uri = data["data"]["generateImage"]["signedUri"]
        logger.debug('Received signed URI: %s', signed_uri)

        # 3) Download the image bytes directly
        logger.debug('Downloading image bytes')
        img_resp = requests.get(signed_uri)
        img_resp.raise_for_status()
        with open(RAW_FILE, 'wb') as f:
            f.write(img_resp.content)
        logger.info('Saved raw image to %s', RAW_FILE)

        ctx.close()
    logger.info('Finished grab_image()')

# ─── IMAGE PROCESSING ──────────────────────────────────────────────────────────
def prep_image():
    logger.info('Starting prep_image()')
    img = Image.open(RAW_FILE)
    w, h = img.size
    logger.debug('Original image size: %dx%d', w, h)

    # Remove watermark strip
    logger.debug('Cropping bottom %d px', CROP_BOTTOM)
    img = img.crop((0, 0, w, h - CROP_BOTTOM))

    # Center square crop
    side = min(img.size)
    left = (img.width - side) // 2
    top  = (img.height - side) // 2
    logger.debug('Center crop box: (%d, %d, %d, %d)', left, top, left+side, top+side)
    img = img.crop((left, top, left + side, top + side))

    # Resize to 1080×1080
    logger.debug('Resizing to 1080×1080')
    img = img.resize((1080, 1080), Image.LANCZOS)
    img.save(OUT_FILE)
    logger.info('Saved processed image to %s', OUT_FILE)

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
    except Exception:
        logger.exception('=== do_post() ERROR ===')
    finally:
        logger.info('Leaving do_post()')

# ─── SCHEDULING ─────────────────────────────────────────────────────────────────
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
    logger.info('Running immediate test post')
    do_post()

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
