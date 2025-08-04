import json, os, random, time
from datetime import datetime
from instagrapi import Client
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

VIDEO_FILENAME = "video.mp4"
SESSION_FILE = "ig_session.json"
CAPTION_BANK = [
    "a space I feel like I’ve been before",
    "the silence in this place is louder than memory",
    "this feels like a dream I forgot",
    "lost between nowhere and nothing",
    "the sound of air and absence",
    "my shadow doesn’t belong here"
]

def log(step):
    print(f"[STEP] {step}")

def login_instagram():
    log("Logging in to Instagram...")
    cl = Client()
    if os.path.exists(SESSION_FILE):
        try:
            cl.load_settings(SESSION_FILE)
            cl.get_timeline_feed()
            log("✅ Loaded IG session.")
            return cl
        except:
            os.remove(SESSION_FILE)

    cl.login(os.getenv("IG_USERNAME"), os.getenv("IG_PASSWORD"))
    cl.dump_settings(SESSION_FILE)
    return cl

def generate_video_on_gemini(prompt="Liminal space with ambient music, no people, surreal dreamlike vibe."):
    log("Starting Gemini video generation...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)

        with open("cookies.json", "r") as f:
            context.add_cookies(json.load(f))

        page = context.new_page()
        page.goto("https://gemini.google.com/app")

        if "accounts.google.com" in page.url:
            raise Exception("Gemini session expired. Update cookies.json")

        prompt_box = page.locator('div[contenteditable="true"][role="textbox"]')
        prompt_box.fill(prompt)
        prompt_box.press("Enter")

        log("Waiting for video to appear...")
        page.wait_for_timeout(10000)

        try:
            page.wait_for_selector("video,img", timeout=120000)
            preview = page.query_selector("video,img")
            if not preview:
                raise Exception("❌ No preview element found.")
            preview.click()
            page.wait_for_timeout(4000)
        except:
            page.screenshot(path="veo_fail_preview.png")
            raise Exception("❌ Failed to click preview element.")

        found = False
        for selector in [
            'mat-icon[fonticon="download"]',
            'button:has(mat-icon[fonticon="download"])',
            '[aria-label="Download"]',
            'text=Download'
        ]:
            try:
                btn = page.locator(selector)
                if btn.is_visible():
                    with page.expect_download() as download_info:
                        btn.click()
                    download = download_info.value
                    download.save_as(VIDEO_FILENAME)
                    log(f"✅ Video downloaded to {VIDEO_FILENAME}")
                    found = True
                    break
            except:
                continue

        if not found:
            page.screenshot(path="veo_fail_download.png")
            raise Exception("❌ Download button not found.")

        browser.close()

def get_caption():
    return random.choice(CAPTION_BANK)

def post_to_instagram():
    log("Preparing Instagram upload...")
    cl = login_instagram()
    caption = get_caption()
    cl.clip_upload(VIDEO_FILENAME, caption)
    log("✅ Video posted to Instagram.")

def run_once():
    try:
        generate_video_on_gemini()
        post_to_instagram()
    except Exception as e:
        print("❌", str(e))

def schedule_posts(n=3):
    hours = sorted(random.sample(range(24), n))
    log(f"Scheduled to post at hours: {hours}")
    while True:
        now = datetime.now().hour
        if now in hours:
            log(f"🕒 Time matched ({now}). Running bot...")
            run_once()
            time.sleep(3600)
        else:
            time.sleep(300)

if __name__ == "__main__":
    run_once()
    schedule_posts(random.randint(1, 4))
