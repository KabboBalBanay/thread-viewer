
import re
from urllib.parse import urlparse, urlencode

import requests
from bs4 import BeautifulSoup
from flask import Flask, redirect, render_template, request

app = Flask(__name__)

HEADERS = {
    "User-Agent": (
        "facebookexternalhit/1.1 "
        "(+http://www.facebook.com/externalhit_uatext.php)"
    ),
    "Accept-Language": "en",
}

THREADS_HOSTS = {
    "threads.net",
    "www.threads.net",
    "threads.com",
    "www.threads.com",
}

POST_PATH = re.compile(r"^/@([\w.]+)/post/([\w-]+)")
SHARED_POST_URL = re.compile(
    r"https?://(?:www\.)?threads\.(?:net|com)"
    r"/@[A-Za-z0-9_.]+/post/[A-Za-z0-9_-]+"
)


def meta(soup, prop):
    tag = soup.find("meta", property=prop)

    if not tag:
        tag = soup.find("meta", attrs={"name": prop})

    if tag and tag.get("content"):
        return tag["content"].strip()

    return None


def fetch_post(username, code):
    # Keep the original extraction strategy.
    # Open Graph descriptions may be previews, not the full post.
    url = f"https://www.threads.net/@{username}/post/{code}"

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=10,
        allow_redirects=True,
    )

    if response.status_code != 200:
        return None

    soup = BeautifulSoup(response.text, "html.parser")

    text = meta(soup, "og:description")
    title = meta(soup, "og:title")

    if not text and not title:
        return None

    images = [
        tag["content"]
        for tag in soup.find_all("meta", property="og:image")
        if tag.get("content")
    ]

    video = meta(soup, "og:video")

    return {
        "username": username,
        "title": title,
        "text": text or title or "",
        "images": images,
        "video": video,
        "original": url,
    }


@app.route("/")
def home():
    return render_template(
        "index.html",
        error=request.args.get("error"),
        shared_text="",
    )


@app.route("/open")
def open_link():
    raw = (request.args.get("url") or "").strip()

    if not raw:
        return redirect("/?error=Please%20paste%20a%20post%20link.")

    if "://" not in raw:
        raw = "https://" + raw

    parsed = urlparse(raw)
    hostname = (parsed.hostname or "").lower()
    match = POST_PATH.match(parsed.path)

    if hostname not in THREADS_HOSTS or not match:
        return redirect(
            "/?" + urlencode({
                "error": "That doesn't look like a Threads post link."
            })
        )

    username, code = match.groups()

    return redirect(
        f"/@{username}/post/{code}"
    )


@app.route("/share", methods=["POST"])
def share():
    # Android/browser share targets can send URL and/or text.
    shared_url = (request.form.get("url") or "").strip()
    shared_text = (request.form.get("text") or "").strip()
    shared_title = (request.form.get("title") or "").strip()

    # Prefer the explicit URL field.
    candidate = shared_url or shared_text

    # A URL may be embedded inside a longer shared text string.
    match = SHARED_POST_URL.search(candidate)

    if match:
        return redirect(
            "/open?" + urlencode({"url": match.group(0)})
        )

    # If no URL exists, show the shared text in an editable field.
    text_to_show = shared_text or shared_url or shared_title

    if not text_to_show:
        return redirect(
            "/?" + urlencode({
                "error": "No link or text was received."
            })
        )

    return render_template(
        "index.html",
        error=None,
        shared_text=text_to_show,
    )


@app.route("/read-text", methods=["POST"])
def read_text():
    text = (request.form.get("text") or "").strip()

    if not text:
        return redirect(
            "/?" + urlencode({"error": "Please paste some text first."})
        )

    return render_template(
        "text.html",
        text=text,
    )


@app.route("/@<username>/post/<code>")
def view_post(username, code):
    try:
        post = fetch_post(username, code)
    except requests.RequestException:
        post = None

    original = f"https://www.threads.net/@{username}/post/{code}"

    if not post:
        return render_template(
            "post.html",
            post=None,
            original=original,
        ), 404

    return render_template(
        "post.html",
        post=post,
        original=post["original"],
    )
