#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Actualiza matches.json con los resúmenes de partidos del Mundial del canal DSports.
Corre en GitHub Actions (del lado del servidor, sin problemas de CORS ni tamaño).
NUNCA borra historia: hace merge con lo que ya había.
"""
import re, json, os, unicodedata, urllib.request
from datetime import datetime, timedelta, timezone

CHANNEL_ID = "UCWSsHdxrwVLlOSdPJ44y9sw"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "matches.json")
CAP = 40
NOW = datetime.now(timezone.utc)

NATIONS = set((
 "argentina|brasil|uruguay|chile|colombia|peru|ecuador|paraguay|bolivia|venezuela|"
 "mexico|estados unidos|canada|costa rica|panama|honduras|jamaica|haiti|el salvador|"
 "guatemala|curazao|espana|francia|inglaterra|alemania|italia|portugal|paises bajos|"
 "holanda|belgica|croacia|suiza|dinamarca|suecia|noruega|polonia|austria|serbia|"
 "escocia|gales|ucrania|turquia|grecia|rumania|hungria|chequia|republica checa|"
 "eslovenia|eslovaquia|irlanda|rusia|marruecos|senegal|tunez|argelia|egipto|nigeria|"
 "ghana|camerun|costa de marfil|sudafrica|mali|cabo verde|angola|rd congo|japon|"
 "corea del sur|corea|australia|arabia saudita|iran|catar|qatar|irak|uzbekistan|"
 "jordania|nueva zelanda|china"
).split("|"))

def norm(s):
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z\s]", " ", s.lower())).strip()

def resolve(s):
    n = norm(s)
    if not n: return None
    if n in NATIONS: return n
    best = None
    for k in NATIONS:
        if len(k) < 4: continue
        if n == k or n.endswith(" " + k) or n.startswith(k + " ") or n.endswith(k) or (" " + n + " ").find(" " + k + " ") >= 0:
            if best is None or len(k) > len(best): best = k
    return best

def extract(title):
    for seg in [s.strip() for s in title.split("|")]:
        m = re.match(r"^(.+?)\s+\d{1,2}\s*[–\-—:]\s*\d{1,2}\s+(.+?)$", seg)
        if m:
            a, b = resolve(m.group(1)), resolve(m.group(2))
            if a and b: return a, b
    return None

def rel_to_iso(txt, idx):
    m = re.search(r"hace\s+(\d+)\s+(minuto|hora|d[ií]a|semana|mes)", txt or "")
    if not m:
        return (NOW - timedelta(hours=(idx + 1))).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    n, u = int(m.group(1)), m.group(2)
    d = {"minuto": timedelta(minutes=n), "hora": timedelta(hours=n), "dia": timedelta(days=n),
         "día": timedelta(days=n), "semana": timedelta(weeks=n), "mes": timedelta(days=30 * n)}[u]
    return (NOW - d).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def fetch(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36",
        "Accept-Language": "es-419,es;q=0.9",
        "Cookie": "CONSENT=YES+1; SOCS=CAI",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", "replace")
    except Exception as e:
        print("  fetch error", url, e)
        return ""

def from_rss(xml):
    out = []
    for e in xml.split("<entry>")[1:]:
        vid = re.search(r"<yt:videoId>([^<]+)", e)
        tit = re.search(r"<title>([\s\S]*?)</title>", e)
        pub = re.search(r"<published>([^<]+)", e)
        if not (vid and tit): continue
        title = (tit.group(1).replace("&amp;", "&").replace("&quot;", '"')
                 .replace("&#39;", "'").replace("&lt;", "<").replace("&gt;", ">"))
        iso = pub.group(1).replace("+00:00", "Z") if pub else ""
        out.append((vid.group(1), title, iso))
    return out

def from_html(html):
    out, i = [], 0
    def add(vid, raw, ctx):
        nonlocal i
        if not (vid and raw): return
        try: title = json.loads('"' + raw + '"')
        except Exception: title = raw
        pubtxt = re.search(r"hace\s+\d+\s+[A-Za-zíÍ]+", ctx)
        out.append((vid, title, rel_to_iso(pubtxt.group(0) if pubtxt else "", i))); i += 1
    for c in html.split('"videoRenderer":{')[1:]:
        vid = re.search(r'"videoId":"([\w-]{11})"', c)
        tt = re.search(r'"title":\{"runs":\[\{"text":"((?:[^"\\]|\\.)*)"', c)
        add(vid.group(1) if vid else None, tt.group(1) if tt else None, c[:1500])
    for c in html.split('"lockupViewModel":{')[1:]:
        vid = re.search(r'"contentId":"([\w-]{11})"', c)
        tt = re.search(r'"lockupMetadataViewModel":\{"title":\{"content":"((?:[^"\\]|\\.)*)"', c)
        add(vid.group(1) if vid else None, tt.group(1) if tt else None, c[:1500])
    return out

def main():
    # carga existente (no perder historia)
    store = {}
    if os.path.exists(OUT):
        try:
            for m in json.load(open(OUT, encoding="utf-8")):
                store[m["id"]] = m
        except Exception as e:
            print("matches.json ilegible:", e)
    print("existentes:", len(store))

    sources = [
        ("rss",  "https://www.youtube.com/feeds/videos.xml?channel_id=" + CHANNEL_ID),
        ("html", "https://www.youtube.com/channel/%s/videos" % CHANNEL_ID),
        ("html", "https://www.youtube.com/channel/%s/search?query=resumen" % CHANNEL_ID),
    ]
    found = 0
    for kind, url in sources:
        data = fetch(url)
        if not data: continue
        items = from_rss(data) if kind == "rss" else from_html(data)
        for vid, title, iso in items:
            mm = extract(title)
            if not (mm and "resumen" in norm(title)): continue
            a, b = mm
            if vid not in store:
                store[vid] = {"id": vid, "a": a, "b": b, "pub": iso}
                found += 1
            elif kind == "rss" and iso:
                store[vid]["pub"] = iso  # el RSS trae fecha exacta
        print("  %s -> %d items" % (url.split("/")[-1][:30], len(items)))

    rows = sorted(store.values(), key=lambda m: m.get("pub", ""), reverse=True)[:CAP]
    json.dump(rows, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("nuevos: %d | total guardado: %d" % (found, len(rows)))

if __name__ == "__main__":
    main()
