from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os, time, re
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from textwrap import wrap
from urllib.parse import urljoin

PAGE_URL = "https://akira.lk/blog/"
SAVE_DIR = "akira_blog_pdfs"
DELAY_SECS = 1.0
MIN_TEXT_LEN = 100

def extract_article_parts(html):
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("h1") or soup.find("h2")
    title = title_tag.get_text(strip=True) if title_tag else "Untitled Article"
    article = soup.select_one("div.blog-detail-content, div.entry-content, article")
    if not article:
        return title, ""
    paragraphs = []
    for p in article.find_all("p"):
        txt = p.get_text(" ", strip=True)
        if txt and len(txt) > 30:
            paragraphs.append(txt)
    text = "\n\n".join(paragraphs)
    text = re.sub(r"Subscribe.*", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"You may also like.*", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"(Contact|About|Privacy|Tel|Phone|Email).*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) < MIN_TEXT_LEN:
        return title, ""
    return title, text

def save_text_to_pdf(title, text, filename):
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    margin = 50
    y = height - margin
    def draw_wrapped_block(txt, bold=False):
        nonlocal y
        for line in wrap(txt, width=90):
            if y < 80:
                c.showPage()
                y = height - margin
            c.setFont("Helvetica-Bold" if bold else "Helvetica", 12 if bold else 11)
            c.drawString(margin, y, line)
            y -= 16
        y -= 10
    draw_wrapped_block(title, bold=True)
    draw_wrapped_block(text)
    c.save()

def crawl_akira_page1():
    os.makedirs(SAVE_DIR, exist_ok=True)
    saved = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"\n🌐 Visiting page 1: {PAGE_URL}")
        page.goto(PAGE_URL, timeout=60000, wait_until="networkidle")
        time.sleep(2)  # extra wait for JS content

        # Get all article links
        raw_links = page.eval_on_selector_all(
            "article.post a", "elements => elements.map(el => el.href)"
        )

        # Deduplicate & filter only real article links
        links = []
        for l in set(raw_links):
            if l.startswith("https://akira.lk/") and "/author/" not in l and "/category/" not in l \
               and "/share" not in l and not l.startswith("whatsapp://") and "pin/create" not in l:
                links.append(l)

        print(f"Found {len(links)} valid articles on page 1.")

        for link in links:
            print(f"\n➡️ Visiting article: {link}")
            try:
                page.goto(link, timeout=60000, wait_until="networkidle")
                time.sleep(1)
                html = page.content()
            except Exception as e:
                print(f"❌ Error loading article: {e}")
                continue

            title, description = extract_article_parts(html)
            if not description:
                print("⚠️ Skipping (no usable content).")
                continue

            saved += 1
            safe_name = re.sub(r"[^\w\d\- ]+", "", title)[:60].strip().replace(" ", "_")
            filename = os.path.join(SAVE_DIR, f"akira_article_{saved}_{safe_name}.pdf")
            try:
                save_text_to_pdf(title, description, filename)
                print(f"[{saved}] ✅ Saved PDF: {filename}")
            except Exception as e:
                print(f"❌ Error saving PDF: {e}")
                continue

            time.sleep(DELAY_SECS)

        browser.close()

    print(f"\n✅ Done. {saved} PDFs saved in '{SAVE_DIR}'.")

if __name__ == "__main__":
    crawl_akira_page1()
