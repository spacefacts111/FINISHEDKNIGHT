import json, os, random, time
from datetime import datetime
from instagrapi import Client
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import subprocess

# Ensure Playwright browsers are installed on startup
subprocess.run(["playwright", "install"], check=False)

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
    log("📲 Logging in to Instagram...")
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
    log("🎨 Starting Gemini video generation...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)

        with open("cookies.json", "r") as f:
            context.add_cookies(json.load(f))

        page = context.new_page()
        log("🌐 Navigating to Gemini Veo...")
        page.goto("https://gemini.google.com/app/veo")

        if "accounts.google.com" in page.url:
            raise Exception("Gemini session expired. Update cookies.json")

        log("🧠 Typing prompt...")
        try:
            page.wait_for_selector('div[contenteditable="true"][role="textbox"]', timeout=15000)
            prompt_box = page.locator('div[contenteditable="true"][role="textbox"]')
            prompt_box.click()
            prompt_box.fill(prompt)
            prompt_box.press("Enter")
        except:
            raise Exception("❌ Could not find Veo prompt box.")

        log("🕒 Waiting for preview to appear...")
        page.wait_for_timeout(10000)

        try:
            page.wait_for_selector("video,img", timeout=120000)
            preview = page.query_selector("video,img")
            if not preview:
                raise Exception("❌ No preview element found.")
            preview.click()
            log("🎬 Preview clicked.")
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
    log("📤 Preparing Instagram upload...")
    cl = login_instagram()
    caption = get_caption()
    cl.clip_upload(VIDEO_FILENAME, caption)
    log("✅ Video posted to Instagram.")

def run_once():
    log("🔁 Starting run_once() loop...")
    try:
        generate_video_on_gemini()
        post_to_instagram()
    except Exception as e:
        print("❌", str(e))

def schedule_posts():
    posted_today = 0
    post_times = sorted(random.sample(range(6, 23), random.randint(1, 4)))
    log(f"🕒 Scheduled random post hours today: {post_times}")
    today = datetime.now().day

    while True:
        now = datetime.now()
        if now.day != today:
            post_times = sorted(random.sample(range(6, 23), random.randint(1, 4)))
            today = now.day
            posted_today = 0
            log(f"🌅 New day! Scheduled post times: {post_times}")

        if now.hour in post_times and posted_today < len(post_times):
            log(f"📸 Time matched: hour {now.hour}. Running bot...")
            run_once()
            posted_today += 1
            time.sleep(3600)
        else:
            time.sleep(300)

if __name__ == "__main__":
    log("🚀 First-time launch: posting immediately...")
    run_once()
    schedule_posts()
