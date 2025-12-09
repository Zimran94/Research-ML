from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os, time, re
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from textwrap import wrap

# Configuration
SAVE_DIR = "life_fashion_90_all_articles"
LISTING_URL = "https://www.life.lk/54/fashion/60"
DELAY_SECS = 1.0
MIN_TEXT_LEN = 50

def extract_article_parts(html):
    soup = BeautifulSoup(html, "html.parser")

    # Title
    title_tag = soup.find("h1") or soup.find("h2")
    title = title_tag.get_text(strip=True) if title_tag else "Untitled Article"

    # Possible containers for content
    selectors = [
        "div.entry-content",
        "div.post-content",
        "article",
        "div.article-body",
        "div.content",
        "div.article-content",
        "div#content"
    ]
    article = None
    for sel in selectors:
        article = soup.select_one(sel)
        if article:
            break

    # fallback to largest block if none matched
    if not article:
        candidates = soup.find_all(["div", "article", "section"], recursive=True)
        best = None
        best_len = 0
        for c in candidates:
            txt = c.get_text(" ", strip=True)
            if len(txt) > best_len:
                best_len = len(txt)
                best = c
        article = best

    if not article:
        return title, ""

    # Remove unwanted tags inside
    for tag in article.find_all(["script", "style", "aside", "figure", "iframe", "noscript"]):
        tag.decompose()

    # Remove elements typical of metadata, author, shares, comments
    for sel in article.select(".share, .social, .related, .author, .post-meta, .byline, .tags, .comments, .subscription, .subscribe"):
        sel.decompose()

    parts = []
    for idx, tag in enumerate(article.find_all(["p", "li"], recursive=True)):
        txt = tag.get_text(" ", strip=True)
        if not txt:
            continue

        # Skip first paragraph if it looks like a date (e.g. “June 5, 2025”)
        if idx == 0 and re.match(r"[A-Za-z]{3,9} \d{1,2}, \d{4}", txt):
            continue

        # Skip short lines & noise
        if len(txt) < 20:
            if len(txt) >= 10:
                parts.append(txt)
            continue

        if re.search(r"(Read more|Subscribe|Follow us|Share this|Related posts|Sponsored|Email address|will be published)", txt, re.I):
            continue

        parts.append(txt)

    text = "\n\n".join(parts).strip()
    text = re.sub(r"\s{2,}", " ", text).strip()

    if len(text) < MIN_TEXT_LEN:
        return title, ""

    return title, text

def save_text_to_pdf(title, text, filename):
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    margin = 50
    y = height - margin

    # Title
    c.setFont("Helvetica-Bold", 14)
    for line in wrap(title, width=80):
        c.drawString(margin, y, line)
        y -= 20
    y -= 8

    # Body text
    c.setFont("Helvetica", 11)
    for line in wrap(text, width=90):
        if y < 80:
            c.showPage()
            y = height - margin
            c.setFont("Helvetica", 11)
        c.drawString(margin, y, line)
        y -= 14

    c.save()

def crawl_all_from_listing(listing_url):
    os.makedirs(SAVE_DIR, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print("Visiting listing page:", listing_url)
        try:
            page.goto(listing_url, timeout=120000, wait_until="domcontentloaded")
            time.sleep(2)
        except Exception as e:
            print("Error loading listing:", e)
            browser.close()
            return

        html = page.content()
        soup = BeautifulSoup(html, "html.parser")

        # Find links to each article — usually inside <a> tags in the listing
        article_links = []
        # In the listing page, each item might use "a" tags under some container
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/article/fashion/" in href or "/54/fashion/" in href:
                full = href if href.startswith("http") else ("https://www.life.lk" + href)
                article_links.append(full)
        article_links = list(set(article_links))
        print("Found article links:", len(article_links))

        count = 0
        for link in article_links:
            print("→ Crawling:", link)
            try:
                page.goto(link, timeout=120000, wait_until="domcontentloaded")
                time.sleep(2)
            except Exception as e:
                print("Error loading article:", e)
                continue

            art_html = page.content()
            title, body = extract_article_parts(art_html)
            if not body:
                print("Skip (no body).")
                continue

            count += 1
            safe = re.sub(r"[^\w\d\- ]+", "", title)[:60].strip().replace(" ", "_")
            filename = os.path.join(SAVE_DIR, f"life_fashion90_{count}_{safe}.pdf")
            try:
                save_text_to_pdf(title, body, filename)
                print("Saved:", filename)
            except Exception as e:
                print("Error saving:", e)

        browser.close()
    print("Done. Total saved:", count)

if __name__ == "__main__":
    crawl_all_from_listing(LISTING_URL)
