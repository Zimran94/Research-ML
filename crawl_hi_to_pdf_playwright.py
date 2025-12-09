from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import os, time, re
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from textwrap import wrap

SEED_URL = "https://www.hi.lk/45/fashion--beauty"
SAVE_DIR = "pdf_pages"
DELAY_SECS = 2.0


def extract_article_parts(html):
    """Extracts title and all main text paragraphs."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove irrelevant tags
    for tag in soup(["script", "style", "noscript", "footer", "header", "nav", "aside"]):
        tag.decompose()

    # Try multiple possible article containers
    selectors = [
        "div.article-content",
        "div.post-content",
        "div.entry-content",
        "div.main-article",
        "div.col-md-8",
        "div.col-lg-8",
        "div.content-container",
        "article",
        "div.content",
        "div.container",
    ]

    article = None
    for sel in selectors:
        article = soup.select_one(sel)
        if article and len(article.get_text(strip=True)) > 100:
            break
    if not article:
        article = soup.find("body")

    # Title
    title_tag = soup.find("h1") or soup.find("h2")
    title = title_tag.get_text(strip=True) if title_tag else "Untitled Article"

    # Paragraphs
    paragraphs = [p.get_text(" ", strip=True) for p in article.find_all("p") if p.get_text(strip=True)]
    if not paragraphs:
        paragraphs = [div.get_text(" ", strip=True) for div in article.find_all("div") if len(div.get_text(strip=True)) > 60]

    # Clean text
    text = "\n\n".join(paragraphs)
    text = re.sub(r"Columnists,.*?- \d{1,2} \w{3} \d{4}", "", text, flags=re.DOTALL)
    text = re.sub(r"ABOUT THE AUTHOR.*", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"You May Also Like.*", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"#\w+", "", text)
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "", text)
    text = re.sub(r"(Contact|Tel|Phone).*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    return title.strip(), text.strip()


def save_text_to_pdf(title, text, filename):
    """Saves title and body to a PDF."""
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    margin = 50
    y = height - margin

    def draw_wrapped(text, bold=False):
        nonlocal y
        for line in wrap(text, width=90):
            if y < 80:
                c.showPage()
                y = height - margin
            c.setFont("Helvetica-Bold" if bold else "Helvetica", 12 if bold else 11)
            c.drawString(margin, y, line)
            y -= 16
        y -= 10

    draw_wrapped(title, bold=True)
    draw_wrapped(text)
    c.save()


def crawl_all_pages():
    os.makedirs(SAVE_DIR, exist_ok=True)
    seen = set()
    saved = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page_num = 1
        while True:
            url = f"{SEED_URL}?page={page_num}" if page_num > 1 else SEED_URL
            print(f"\n🌐 Visiting page {page_num}: {url}")
            page.goto(url, timeout=90000)
            page.wait_for_load_state("networkidle")
            soup = BeautifulSoup(page.content(), "html.parser")

            # Collect article links
            links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.startswith("/article") or "/fashion" in href:
                    full_url = "https://www.hi.lk" + href if href.startswith("/") else href
                    if full_url not in seen:
                        seen.add(full_url)
                        links.append(full_url)

            if not links:
                print("🚫 No more articles found. Exiting pagination loop.")
                break

            print(f"Found {len(links)} articles on page {page_num}.")

            for link in links:
                try:
                    print(f"\nVisiting article: {link}")
                    page2 = browser.new_page()
                    page2.goto(link, timeout=90000)

                    # Scroll to load content
                    for _ in range(12):
                        page2.mouse.wheel(0, 2000)
                        time.sleep(0.8)

                    time.sleep(2.5)

                    html = page2.content()
                    title, article_text = extract_article_parts(html)

                    if not article_text or len(article_text) < 300:
                        print("⚠️ Skipping (too short).")
                        page2.close()
                        continue

                    saved += 1
                    filename = os.path.join(SAVE_DIR, f"page_{saved}.pdf")
                    save_text_to_pdf(title, article_text, filename)
                    print(f"[{saved}] ✅ Saved PDF: {filename}")
                    page2.close()

                except Exception as e:
                    print(f"❌ Error on {link}: {e}")
                    continue

                time.sleep(DELAY_SECS)

            page_num += 1

        browser.close()
    print(f"\n✅ Done. {saved} PDFs saved in '{SAVE_DIR}'.")


if __name__ == "__main__":
    crawl_all_pages()
