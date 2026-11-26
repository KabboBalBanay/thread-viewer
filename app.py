import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from flask import Flask, redirect, render_template, request

app = Flask(__name__)

# Threads serves meta tags (og:*) to link-preview bots, no login needed.
HEADERS = {
    "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
    "Accept-Language": "en",
}
THREADS_HOSTS = {"threads.net", "www.threads.net", "threads.com", "www.threads.com"}
POST_PATH = re.compile(r"^/@([\w.]+)/post/([\w-]+)")


def meta(soup, prop):
    tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
    return tag["content"].strip() if tag and tag.get("content") else None


def fetch_post(username, code):
    url = f"https://www.threads.net/@{username}/post/{code}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    if r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    text = meta(soup, "og:description")
    title = meta(soup, "og:title")
    if not text and not title:
        return None
    images = [t["content"] for t in soup.find_all("meta", property="og:image") if t.get("content")]
    video = meta(soup, "og:video")
    return {
        "username": username,
        "title": title,
        "text": text,
        "images": images,
        "video": video,
        "original": url,
    }


@app.route("/")
def home():
    return render_template("index.html", error=request.args.get("error"))


@app.route("/open")
def open_link():
    raw = (request.args.get("url") or "").strip()
    if raw and "://" not in raw:
        raw = "https://" + raw
    p = urlparse(raw)
    m = POST_PATH.match(p.path)
    if p.netloc.lower() not in THREADS_HOSTS or not m:
        return redirect("/?error=That doesn't look like a Threads post link.")
    return redirect(f"/@{m.group(1)}/post/{m.group(2)}")


@app.route("/@<username>/post/<code>")
def view_post(username, code):
    try:
        post = fetch_post(username, code)
    except requests.RequestException:
        post = None
    if not post:
        return render_template(
            "post.html", post=None,
            original=f"https://www.threads.net/@{username}/post/{code}",
        ), 404
    return render_template("post.html", post=post, original=post["original"])
