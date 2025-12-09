from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os, time, re
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from textwrap import wrap

SAVE_DIR = "weekendfashionista_articles"
DELAY_SECS = 1.0
MIN_TEXT_LEN = 100

def extract_article_parts(html):
    soup = BeautifulSoup(html, "html.parser")
    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else "Untitled Article"

    article = soup.select_one("div.entry-content")
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

    # ✅ Always set font before drawing first text
    c.setFont("Helvetica-Bold", 14)
    for line in wrap(title, width=80):
        c.drawString(margin, y, line)
        y -= 20
    y -= 10

    c.setFont("Helvetica", 11)
    for line in wrap(text, width=90):
        if y < 80:
            c.showPage()
            y = height - margin
            c.setFont("Helvetica", 11)
        c.drawString(margin, y, line)
        y -= 14

    c.save()


def crawl_weekendfashionista(page_url, start_index=1):
    os.makedirs(SAVE_DIR, exist_ok=True)
    saved = start_index - 1

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        print(f"\n🌐 Visiting page: {page_url}")
        try:
            page.goto(page_url, timeout=120000, wait_until="domcontentloaded")
        except Exception as e:
            print(f"❌ Error loading page: {e}")
            browser.close()
            return

        time.sleep(2)

        raw_links = page.eval_on_selector_all(
            "h2.entry-title a", "elements => elements.map(el => el.href)"
        )

        links = list(set(raw_links))
        print(f"Found {len(links)} valid articles on page.")

        for link in links:
            print(f"\n➡️ Visiting article: {link}")
            try:
                page.goto(link, timeout=120000, wait_until="domcontentloaded")
                time.sleep(2)
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
            filename = os.path.join(SAVE_DIR, f"weekendfashionista_article_{saved}_{safe_name}.pdf")

            try:
                save_text_to_pdf(title, description, filename)
                print(f"[{saved}] ✅ Saved PDF: {filename}")
            except Exception as e:
                print(f"❌ Error saving PDF: {e}")

            time.sleep(DELAY_SECS)

        browser.close()

    print(f"\n✅ Done. {saved} PDFs saved in '{SAVE_DIR}'.")


if __name__ == "__main__":
    crawl_weekendfashionista("https://theweekendfashionista.com/category/fashion/weekend-style/", start_index=1)
