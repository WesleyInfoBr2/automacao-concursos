# -*- coding: utf-8 -*-
"""
Scraper PCI Concursos (filtrado)
- Página: https://www.pciconcursos.com.br/concursos/
- Saída: JSONL apenas para itens com:
    - maior salário mencionado >= MIN_SALARY
    - e inscrição aberta (prazo final >= hoje)
Campos: title, url, source, kind, deadline, deadline_end_iso, salary_max, location, summary, description
"""

import sys
import re
import time
import json
from datetime import datetime, date
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

# --------- Config ---------
MIN_SALARY = 10000  # filtrar por salário mínimo desejado (R$)
MAX_ITEMS  = 200
SLEEP_BETWEEN = 0.7
# --------------------------

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = "https://www.pciconcursos.com.br/"
LIST_URL = urljoin(BASE, "concursos/")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/123.0 Safari/537.36"
}

IGNORE_TITLES = {
    "Concursos", "Nacional", "Sudeste", "Sul", "Norte", "Nordeste", "Centro-Oeste",
    "Área Jurídica", "Área de Saúde", "Área de Educação", "Área Administrativa",
    "Prefeituras", "Câmaras", "Militar", "Polícia", "Bancos"
}
IGNORE_HREF_PATTERNS = (
    "/concursos/nacional/", "/concursos/sudeste/", "/concursos/sul/",
    "/concursos/norte/", "/concursos/nordeste/", "/concursos/centro-oeste/",
    "/concursos/area-", "/concursos/busca", "/concursos/cursos", "/cursos/"
)

DATE_PAT = re.compile(
    r"(?:(?:inscri(?:ç|c)[õo]es?|prazo|per[ií]odo|encerramento).{0,60})?"
    r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    r"(?:\s*(?:a|até|–|-|ao)\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4})?)",
    flags=re.I | re.S
)
DATE_TEXT_PAT = re.compile(
    r"(\d{1,2})\s+de\s+(janeiro|fevereiro|março|marco|abril|maio|junho|julho|"
    r"agosto|setembro|outubro|novembro|dezembro)\s+de\s+(\d{4})",
    flags=re.I
)

# R$ 12.345,67 | R$12.000 | até R$ 18.000 | R$ 9.000 a R$ 14.000
SAL_PAT = re.compile(
    r"R\$\s*([0-9.\s]+(?:,[0-9]{2})?)"
    r"(?:\s*(?:a|até|-|–|ao)\s*R?\$?\s*([0-9.\s]+(?:,[0-9]{2})?))?",
    flags=re.I
)

MONTHS = {
    'janeiro':1,'fevereiro':2,'março':3,'marco':3,'abril':4,'maio':5,'junho':6,
    'julho':7,'agosto':8,'setembro':9,'outubro':10,'novembro':11,'dezembro':12
}

def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())

def looks_like_menu(title: str, href: str) -> bool:
    t = (title or "").strip()
    if not t:
        return True
    if t in IGNORE_TITLES:
        return True
    href = href or ""
    for frag in IGNORE_HREF_PATTERNS:
        if frag in href:
            return True
    if len(t) < 8:
        return True
    return False

def money_to_float(txt: str) -> float | None:
    if not txt:
        return None
    val = txt.replace(".", "").replace(" ", "").replace("\xa0","")
    val = val.replace(",", ".")
    try:
        return float(val)
    except Exception:
        return None

def extract_salary_max(text: str) -> float | None:
    """Retorna o MAIOR salário (em R$) encontrado no texto."""
    if not text:
        return None
    mx = None
    for m in SAL_PAT.finditer(text):
        a = money_to_float(m.group(1))
        b = money_to_float(m.group(2)) if m.group(2) else None
        cand = max([x for x in (a, b) if isinstance(x, (int,float))], default=None)
        if cand is not None:
            mx = cand if (mx is None or cand > mx) else mx
    return mx

def parse_dates_from_text(text: str) -> tuple[date|None, date|None, str|None]:
    """Tenta extrair intervalo/última data (numérico e textual)."""
    if not text:
        return None, None, None
    text_norm = norm(text)

    # 1) datas numéricas
    nums = re.findall(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", text_norm)
    dates = []
    for d, m, y in nums:
        dd = int(d); mm = int(m); yy = int(y)
        if yy < 100: yy += 2000
        try:
            dates.append(date(yy, mm, dd))
        except Exception:
            pass

    # 2) datas textuais
    for d, mon, y in DATE_TEXT_PAT.findall(text_norm):
        mm = MONTHS.get(mon.lower(), None)
        if mm:
            try:
                dates.append(date(int(y), mm, int(d)))
            except Exception:
                pass

    if not dates:
        # nenhuma ISO possível
        return None, None, None

    # heurística: usa menor como início e maior como fim
    d_start = min(dates)
    d_end   = max(dates)
    return d_start, d_end, None  # deadline_text já está no texto original

def get(url: str) -> requests.Response:
    r = requests.get(url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r

def parse_list():
    r = get(LIST_URL)
    soup = BeautifulSoup(r.text, "html.parser")
    candidates, seen = [], set()

    for a in soup.select("a[href]"):
        href = a.get("href") or ""
        title = norm(a.get_text())
        if not href or not title:
            continue
        url = urljoin(BASE, href) if href.startswith("/") else href
        if not ("/noticias/" in url or "/concursos/" in url):
            continue
        if looks_like_menu(title, url):
            continue

        parent = a.find_parent(["article","li","div"])
        wrap_text = norm(parent.get_text()) if parent else title

        deadline_guess = None
        m = DATE_PAT.search(wrap_text)
        if m:
            deadline_guess = norm(m.group(1))

        key = (title.lower(), url)
        if key in seen: 
            continue
        seen.add(key)

        candidates.append({
            "title": title[:200],
            "url": url,
            "summary": wrap_text[:1000],
            "deadline_guess": deadline_guess,
        })
        if len(candidates) >= MAX_ITEMS:
            break
    return candidates

def parse_detail(url: str) -> tuple[str, str]:
    """Retorna (description, deadline_text_melhorado)."""
    try:
        time.sleep(SLEEP_BETWEEN)
        r = get(url)
    except Exception:
        return "", ""
    soup = BeautifulSoup(r.text, "html.parser")

    article = (soup.select_one("article")
               or soup.select_one("div#content")
               or soup.select_one("div.content")
               or soup.select_one("section")
               or soup.select_one("div[id*='conteudo'], div[class*='conteudo']"))

    if article:
        tx = " ".join(norm(p.get_text()) for p in article.find_all(["p","li"]) if norm(p.get_text()))
        raw = norm(article.get_text(separator=" "))
    else:
        tx = " ".join(norm(p.get_text()) for p in soup.find_all("p") if norm(p.get_text()))
        raw = norm(soup.get_text())

    # tenta achar texto de prazo mais confiável
    m = DATE_PAT.search(raw) or DATE_PAT.search(tx)
    deadline_text = norm(m.group(1)) if m else ""
    description = tx if tx else raw
    return description[:15000], deadline_text

def main():
    today = date.today()
    items = parse_list()

    for it in items:
        desc, deadline_detail_text = parse_detail(it["url"])
        # texto para analisar salário
        text_for_salary = " ".join([it.get("summary",""), desc])

        salary_max = extract_salary_max(text_for_salary)
        if salary_max is None or salary_max < MIN_SALARY:
            continue  # pula salários abaixo do corte ou ausentes

        # prioridade: prazo do detalhe; fallback: prazo da lista
        deadline_text = deadline_detail_text or it.get("deadline_guess") or ""
        d_start, d_end, _ = parse_dates_from_text(deadline_text)

        # precisa ter data final válida e estar >= hoje
        if not d_end or d_end < today:
            continue

        out = {
            "title": it["title"],
            "url": it["url"],
            "source": "PCI Concursos",
            "kind": "Concurso",
            "deadline": deadline_text or None,
            "deadline_end_iso": d_end.isoformat(),
            "salary_max": salary_max,
            "location": "",
            "summary": it["summary"][:800],
            "description": desc,
        }
        print(json.dumps(out, ensure_ascii=False))

if __name__ == "__main__":
    main()
