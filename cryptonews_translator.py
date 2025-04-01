import os
import requests
import json
import time
from datetime import datetime

# Environment Variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN")
FB_PAGE_ACCESS_TOKEN = os.getenv("FB_PAGE_ACCESS_TOKEN")  # Optional for now
FB_PAGE_ID = os.getenv("FB_PAGE_ID")  # Optional for now

# Gemini prompt template
GEMINI_PROMPT_TEMPLATE = """
Translate the following news into Malay.  
Then, kindly write a short conclusion or summary of the news in less than 280 characters in 1 paragraph.  
Only return the short conclusion without any explanation. 
Use natural, conversational, friendly Malaysian Malay — like how a friend shares info. 
Keep it simple, relaxed, and easy to understand. 
Avoid using exaggerated slang words or interjections (such as "Eh," "Korang," "Woi," "Wooohooo," "Wooo," or anything similar). 
No shouting words or unnecessary excitement. 
Keep it informative, approachable, and casual — but clean and neutral. 
Do not use emojis unless they appear in the original text. 
Do not translate brand names or product names.

Original news:
'{text}'
"""

# Translate text using Gemini API
def translate_text_gemini(text):
    if not text or not isinstance(text, str) or not text.strip():
        return "Translation failed"

    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    prompt_text = GEMINI_PROMPT_TEMPLATE.format(text=text)

    payload = {
        "contents": [{
            "parts": [{
                "text": prompt_text
            }]
        }]
    }

    for attempt in range(5):
        try:
            response = requests.post(gemini_url, headers=headers, json=payload)
            if response.status_code == 200:
                data = response.json()
                translated = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                return translated.strip() if translated else "Translation failed"
            elif response.status_code == 429:
                print(f"[Rate Limit] Retrying in {2 ** attempt} seconds...")
                time.sleep(2 ** attempt)
            else:
                print(f"[Gemini Error] {response.status_code}: {response.text}")
                return "Translation failed"
        except Exception as e:
            print(f"[Gemini Exception] {e}")
            return "Translation failed"
    return "Translation failed"

# Fetch all crypto news from Apify
def fetch_news_from_apify():
    url = f"https://api.apify.com/v2/acts/buseta~crypto-news/run-sync-get-dataset-items?token={APIFY_API_TOKEN}"
    try:
        response = requests.post(url, timeout=600)
        if response.status_code == 201:
            return response.json()
        else:
            print(f"[Apify Error] {response.status_code}: {response.text}")
            return []
    except Exception as e:
        print(f"[Apify Exception] {e}")
        return []

# Post text to Facebook (if configured)
def post_to_facebook(message):
    if not FB_PAGE_ACCESS_TOKEN or not FB_PAGE_ID:
        print("[INFO] Facebook configuration not found. Skipping posting.")
        return False

    fb_api_url = f"https://graph.facebook.com/{FB_PAGE_ID}/feed"
    post_data = {
        "message": message,
        "access_token": FB_PAGE_ACCESS_TOKEN
    }

    response = requests.post(fb_api_url, data=post_data)
    if response.status_code == 200:
        print(f"[Post Success]")
        return True
    else:
        print(f"[Post Error] {response.status_code}: {response.text}")
        return False

# Save translated content (before posting)
def save_to_json(news_list, filename="translated_news.json"):
    output = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "all_news": news_list
    }
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=4)
    print(f"[JSON Saved] {filename}")

# Main function
def main():
    if not APIFY_API_TOKEN or not GEMINI_API_KEY:
        print("[ERROR] APIFY_API_TOKEN or GEMINI_API_KEY missing!")
        return

    fetched_news = fetch_news_from_apify()
    translated_news = []

    for idx, news in enumerate(fetched_news):
        print(f"\nProcessing news {idx + 1} of {len(fetched_news)}")

        original_url = news.get("link") or ""
        content_to_translate = f"{news.get('title', '')}\n\n{news.get('summary', '')}\n\n{news.get('content', '')}\n\nSumber asal: {original_url}"

        translated_fb_post = translate_text_gemini(content_to_translate)

        if translated_fb_post == "Translation failed":
            print(f"[SKIP] Translation failed for news {idx + 1}. Skipping this news.")
            continue

        post_success = False
        # Only attempt post if FB config exists
        if FB_PAGE_ACCESS_TOKEN and FB_PAGE_ID:
            post_success = post_to_facebook(translated_fb_post)
        else:
            print("[INFO] Facebook post skipped. Just saving to JSON for review.")

        translated_news.append({
            "original_url": original_url,
            "translated_facebook_post": translated_fb_post,
            "timestamp": news.get("time", datetime.now().isoformat()),
            "status": "Posted" if post_success else "Ready for post"
        })

        time.sleep(1)

    save_to_json(translated_news)

if __name__ == "__main__":
    main()
