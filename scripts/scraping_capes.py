# scraping_capes.py
import json, re
import sys
sys.stdout.reconfigure(encoding='utf-8')
from playwright.sync_api import sync_playwright

BASE = "https://www.gov.br/capes/pt-br/acesso-a-informacao/licitacoes-e-contratos/chamadas-publicas/chamadas"

def norm(s): 
    return re.sub(r"\s+", " ", (s or "").strip())

def run():
    out = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        page = b.new_page()
        page.goto(BASE, timeout=120000)
        page.wait_for_load_state("domcontentloaded")
        # Estruturas no gov.br costumam ter cards/itens <a> com título
        items = page.locator("a[href]").element_handles()
        seen = set()
        for a in items:
            href = a.get_attribute("href") or ""
            text = norm(a.inner_text())
            if not text or "chamada" not in text.lower(): 
                continue
            if href.startswith("/"):
                href = "https://www.gov.br" + href
            key = text + "|" + href
            if key in seen: 
                continue
            seen.add(key)
            wrap = a.evaluate("el => el.closest('article,li,div')?.innerText || ''") or ""
            # tenta achar PDF e prazo
            pdf = None
            if href.lower().endswith(".pdf"): 
                pdf = href
            deadline = None
            m = re.search(r"(?i)(prazo|encerramento|inscri(?:ç|c)ões).*?(\\d{1,2}[\\/-]\\d{1,2}[\\/-]\\d{2,4})", wrap)
            if m:
                deadline = norm(m.group(2))
            out.append({
                "title": text[:200],
                "url": pdf or href,
                "source": "CAPES",
                "kind": "Chamada/Bolsa",
                "deadline": deadline,
                "location": "Brasil",
                "summary": norm(wrap)[:800]
            })
        b.close()
    for it in out:
        print(json.dumps(it, ensure_ascii=False))

if __name__ == "__main__":
    run()
