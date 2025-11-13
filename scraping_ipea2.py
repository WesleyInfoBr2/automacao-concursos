# -*- coding: utf-8 -*-
"""
IPEA (Bolsas de Pesquisa) — lista + detalhe, restrito a:
  - https://www.ipea.gov.br/portal/bolsas-de-pesquisa
  - subpáginas cujos paths começam com:
      /portal/bolsas-de-pesquisa
      /portal/bolsas-de-pesquisa-lista/

Saída (JSONL por linha):
  title, url, source, kind, deadline, location, summary, description, status, program, year
"""

import sys
import re
import time
import json
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

# --- saída UTF-8 no Windows ---
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = "https://www.ipea.gov.br"
START_URL = "https://www.ipea.gov.br/portal/bolsas-de-pesquisa"
ALLOWED_PATH_PREFIXES = (
    "/portal/bolsas-de-pesquisa",
    "/portal/bolsas-de-pesquisa-lista/",
)

SOURCE   = "IPEA"
KIND     = "Bolsa"
LOCATION = "Brasil"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/123.0 Safari/537.36"
}

MAX_ITEMS = 120
SLEEP_LIST   = 0.5
SLEEP_DETAIL = 0.7

# regex de datas (numérico e textual)
DATE_NUM_PAT = re.compile(
    r"(?:(?:inscri(?:ç|c)[õo]es?|prazo|per[íi]odo|submiss(?:ão|ões)|encerramento).{0,80})?"
    r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    r"(?:\s*(?:a|até|–|-|ao)\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4})?)",
    flags=re.I | re.S
)
DATE_TEXT_PAT = re.compile(
    r"(\d{1,2}\s+de\s+[A-Za-zçãéêíóôúà]+\s+de\s+\d{4}"
    r"(?:\s*(?:a|até|–|-|ao)\s*\d{1,2}\s+de\s+[A-Za-zçãéêíóôúà]+\s+de\s+\d{4})?)",
    flags=re.I
)

def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def extract_deadline(text: str) -> str | None:
    if not text:
        return None
    m = DATE_NUM_PAT.search(text)
    if m:
        return norm(m.group(1))
    m2 = DATE_TEXT_PAT.search(text)
    if m2:
        return norm(m2.group(1))
    return None

def is_allowed(url: str) -> bool:
    """Permite APENAS páginas do host ipea.gov.br com path autorizado."""
    if not url:
        return False
    u = urlparse(url)
    if u.scheme not in ("http", "https"):
        return False
    if u.netloc not in ("ipea.gov.br", "www.ipea.gov.br"):
        return False
    if not any(u.path.startswith(prefix) for prefix in ALLOWED_PATH_PREFIXES):
        return False
    return True

def get(url: str) -> requests.Response:
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r

def parse_listing():
    """Lê a página de bolsas e retorna items da lista."""
    r = get(START_URL)
    soup = BeautifulSoup(r.text, "html.parser")
    ul = soup.select_one("ul.search-resultsbolsas.list-striped")
    if not ul:
        return []

    items = []
    seen = set()

    for li in ul.select("li"):
        # título + link
        a = li.select_one("h4.result-title a[href]")
        if not a:
            continue
        title = norm(a.get_text())
        href = a.get("href") or ""
        url = urljoin(BASE, href)

        if not is_allowed(url) or not title:
            continue

        # campos auxiliares na lista
        objetivo_p = li.select_one("p.objetivo")
        summary = norm(objetivo_p.get_text()) if objetivo_p else title

        status = program = year = None
        for p in li.find_all("p"):
            txt = norm(p.get_text())
            low = txt.lower()
            if low.startswith("situação:"):
                status = norm(txt.split(":", 1)[-1])
            elif low.startswith("programa:"):
                program = norm(txt.split(":", 1)[-1])
            elif low.startswith("ano:"):
                year = norm(txt.split(":", 1)[-1])

        # prazo na listagem
        deadline = None
        prazos = [p for p in li.find_all("p") if "Prazo de inscrição" in p.get_text()]
        if prazos:
            deadline = extract_deadline(prazos[0].get_text())
        if not deadline:
            # fallback: tenta em todo o li
            deadline = extract_deadline(li.get_text())

        key = (title.lower(), url)
        if key in seen:
            continue
        seen.add(key)

        items.append({
            "title": title[:200],
            "url": url,
            "summary": summary[:800],
            "status": status,
            "program": program,
            "year": year,
            "deadline_guess": deadline
        })

        if len(items) >= MAX_ITEMS:
            break

    return items

def parse_detail(url: str) -> tuple[str, str, dict]:
    """
    Abre a página de detalhe e extrai:
    - description: texto principal (div[itemprop='articleBody'] prioritário)
    - deadline_detail: prazo (se houver)
    - meta: dict com chaves adicionais que achar (situação, ano, programa, etc.)
    """
    if not is_allowed(url):
        return "", None, {}

    time.sleep(SLEEP_DETAIL)
    r = get(url)
    soup = BeautifulSoup(r.text, "html.parser")

    # corpo principal
    body = soup.select_one("div[itemprop='articleBody']")
    description = ""
    if body:
        description = norm(body.get_text(separator=" "))
    else:
        # fallback: pega tudo da área principal
        main = soup.select_one("main") or soup.select_one("article") or soup.select_one("div#content") or soup
        description = norm(main.get_text(separator=" "))

    deadline_detail = extract_deadline(description)

    # metadados da lateral/box
    meta = {}
    info = soup.select_one("div.informacoes-bolsa")
    if info:
        info_txt = norm(info.get_text(separator=" "))
        # tenta mapear campos simples
        for p in info.find_all("p"):
            txt = norm(p.get_text())
            if ":" in txt:
                k, v = txt.split(":", 1)
                meta[k.strip().lower()] = v.strip()
        # tentativa de sobrescrever prazo com algo mais claro
        if not deadline_detail:
            for k, v in meta.items():
                if "prazo" in k:
                    deadline_detail = extract_deadline(v) or deadline_detail

    return description[:15000], deadline_detail, meta

def main():
    rows = []
    # 1) lista
    candidates = parse_listing()

    # 2) detalhe por item
    for it in candidates:
        try:
            desc, dedl, meta = parse_detail(it["url"])
        except Exception:
            desc, dedl, meta = "", None

        deadline = dedl or it.get("deadline_guess")
        status = it.get("status")
        program = it.get("program")
        year = it.get("year")

        # se vierem valores melhores do detalhe:
        if meta:
            status = meta.get("situação") or status or meta.get("situação ")
            program = meta.get("programa") or program
            year = meta.get("ano") or year
            if not deadline:
                # mais uma tentativa com qualquer valor de meta
                joined = " ".join(meta.values())
                deadline = extract_deadline(joined) or deadline

        row = {
            "title": it["title"],
            "url": it["url"],
            "source": SOURCE,
            "kind": KIND,
            "deadline": deadline,
            "location": LOCATION,
            "summary": it["summary"],
            "description": desc,
            "status": status,
            "program": program,
            "year": year
        }
        rows.append(row)

    # imprime JSONL
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))

if __name__ == "__main__":
    main()
