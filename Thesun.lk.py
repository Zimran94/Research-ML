from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os, time, re
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from textwrap import wrap

# -------- CONFIG --------
SAVE_DIR = "thesun_article_pdfs"
DELAY_SECS = 1.0
MIN_TEXT_LEN = 50   # allow shorter articles if needed
ARTICLE_URL = "https://www.thesun.lk/front_page/The-Fast-Fashion-Blame-Game-Us-or-Them/557-304072"
# ------------------------

def extract_article_parts(html):
    soup = BeautifulSoup(html, "html.parser")

    # Try typical title selectors
    title_tag = soup.find("h1") or soup.find("h2") or soup.select_one(".entry-title") or soup.select_one(".post-title")
    title = title_tag.get_text(strip=True) if title_tag else "Untitled Article"

    # Try multiple common main-content selectors used by news/blog sites
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

    # Fallback: pick the largest text block
    if not article:
        candidates = soup.find_all(["div", "article", "section"], recursive=True)
        max_len = 0
        for c in candidates:
            txt = c.get_text(" ", strip=True)
            if len(txt) > max_len:
                max_len = len(txt)
                article = c

    if not article:
        return title, ""

    for bad in article.find_all(["script", "style", "aside", "figure", "iframe", "noscript"]):
        bad.decompose()

    for sel in article.select(".share, .social, .related, .author, .post-meta, .byline, .tags, .subscription, .subscribe"):
        sel.decompose()

    parts = []
    for tag in article.find_all(["p", "li"], recursive=True):
        txt = tag.get_text(" ", strip=True)
        if not txt:
            continue
        if len(txt) < 20:
            if len(txt) >= 10:
                parts.append(txt)
            continue
        if re.search(r"(Read more|Subscribe|Follow us|Share this|Related posts|Sponsored)", txt, re.I):
            continue
        parts.append(txt)

    text = "\n\n".join(parts).strip()
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"(Click here to read.*)", "", text, flags=re.I)
    text = text.strip()

    if len(text) < MIN_TEXT_LEN:
        return title, ""

    return title, text

def save_text_to_pdf(title, text, filename):
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    margin = 50
    y = height - margin

    c.setFont("Helvetica-Bold", 14)
    for line in wrap(title, width=80):
        c.drawString(margin, y, line)
        y -= 20
    y -= 8

    c.setFont("Helvetica", 11)
    for line in wrap(text, width=90):
        if y < 80:
            c.showPage()
            y = height - margin
            c.setFont("Helvetica", 11)
        c.drawString(margin, y, line)
        y -= 14

    c.save()

def crawl_single_article(url, save_dir):
    os.makedirs(save_dir, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"Opening: {url}")
        try:
            page.goto(url, timeout=120000, wait_until="domcontentloaded")
            time.sleep(2)
        except Exception as e:
            print("Error loading page:", e)
            browser.close()
            return

        html = page.content()
        title, body = extract_article_parts(html)

        if not body:
            print("No article body extracted. Adjust selectors if needed.")
            browser.close()
            return

        safe_name = re.sub(r"[^\w\d\- ]+", "", title)[:60].strip().replace(" ", "_")
        filename = os.path.join(save_dir, f"thesun_article_{safe_name}.pdf")

        try:
            save_text_to_pdf(title, body, filename)
            print("✅ Saved PDF:", filename)
        except Exception as e:
            print("Error saving PDF:", e)

        browser.close()

if __name__ == "__main__":
    crawl_single_article(ARTICLE_URL, SAVE_DIR)
