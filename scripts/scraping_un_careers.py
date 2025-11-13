# scraping_un_careers.py
import json, re
import sys
sys.stdout.reconfigure(encoding='utf-8')
from playwright.sync_api import sync_playwright

BASE = "https://careers.un.org"

def norm(s): 
    return re.sub(r"\s+", " ", (s or "").strip())

def run():
    out = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        page = b.new_page()
        page.goto(BASE + "/jobopening", timeout=120000)
        page.wait_for_load_state("domcontentloaded")
        # os cards costumam ter anchors para jobdetail
        cards = page.locator("a[href*='jobdetail']").element_handles()
        for a in cards[:120]:
            href = a.get_attribute("href") or ""
            if href.startswith("/"):
                href = BASE + href
            title = norm(a.inner_text())
            if not title:
                # alternativa: extrair do contêiner
                title = norm(a.evaluate("el => el.closest('div')?.innerText || ''"))
            # tenta capturar dados ao redor (deadline, duty station)
            box = a.evaluate("el => el.closest('div')?.innerText || ''") or ""
            deadline = None
            m = re.search(r"(?i)(Deadline|Closing|Closes)\\D{0,10}([\\w\\s,:-]+\\d{4})", box)
            if m:
                deadline = norm(m.group(2))
            loc = None
            m2 = re.search(r"(?i)(Duty Station|Location)\\D{0,5}([\\w\\s,/-]+)", box)
            if m2:
                loc = norm(m2.group(2))
            out.append({
                "title": title[:200],
                "url": href,
                "source": "UN Careers",
                "kind": "Internacional",
                "deadline": deadline,
                "location": loc or "",
                "summary": norm(box)[:800]
            })
        b.close()
    for it in out:
        print(json.dumps(it, ensure_ascii=False))

if __name__ == "__main__":
    run()
