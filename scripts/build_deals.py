#!/usr/bin/env python3
"""Bygger deals.json for tilbudssiden: siste BonusShop-poster fra Zernio + Ukens deal fra Awin."""
import json, os, re, urllib.request, datetime

ROOT = os.path.join(os.path.dirname(__file__), "..")
KEY = os.environ.get("ZERNIO_KEY", "").strip()
AWIN_JSON = "https://raw.githubusercontent.com/Sunnere/bonusvarsel/local-stable-baseline/data/awin-deals.json"
MAX_AGE_DAYS = 4

def norm(s):
    s = s.lower().replace("å", "a").replace("ø", "o").replace("æ", "ae").replace("ö", "o").replace("é", "e")
    s = re.sub(r"\.(no|com|eu)\b", "", s)
    return re.sub(r"[^a-z0-9]", "", s)

def get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": "tilbud-bot"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))

def main():
    brands = json.load(open(os.path.join(ROOT, "brands.json")))
    index = sorted(((norm(b["name"]), b) for b in brands), key=lambda x: -len(x[0]))
    def find_brand(text):
        t = norm(text)
        for k, b in index:
            if len(k) >= 3 and k in t:
                return b
        return None

    deals, seen = [], set()
    now = datetime.datetime.now(datetime.timezone.utc)

    # 1) Ukens deal (produktlenker)
    try:
        aw = get(AWIN_JSON)
        for d in aw.get("deals", []):
            if re.search(r"no_selection|placeholder|noimage", d.get("image", ""), re.I):
                continue
            deals.append({"brand": d["brand"], "title": d["headline"], "text": d["price_text"],
                          "image": d["media_url"], "url": d["link"], "type": "produkt",
                          "date": aw.get("generated", "")})
    except Exception as e:
        print("Awin-feil:", e)

    # 2) Kavalkader fra Zernio (kun Instagram-postene, de er like TikTok)
    if KEY:
        try:
            posts = get("https://zernio.com/api/v1/posts?limit=30", {"Authorization": f"Bearer {KEY}", "User-Agent": "tilbud-bot"}).get("posts", [])
        except Exception as e:
            print("Zernio-feil (sjekk ZERNIO_KEY):", e)
            posts = []
        for p in posts:
            if "instagram" not in [x.get("platform") for x in p.get("platforms", [])]:
                continue
            created = datetime.datetime.fromisoformat(p["createdAt"].replace("Z", "+00:00"))
            if (now - created).days > MAX_AGE_DAYS:
                continue
            content = p.get("content") or ""
            if content.startswith("Reklame"):
                continue  # Ukens deal er allerede med som produkter
            imgs = [m["url"] for m in p.get("mediaItems", []) if "flyhjelp" not in m["url"]]
            lines = [l.strip() for l in content.splitlines() if " – " in l or " - " in l]
            i = 0
            for l in lines:
                b = find_brand(l.split("–")[0].split(" - ")[0])
                if not b or "flyhjelp" in norm(b["name"]):
                    continue
                key = norm(b["name"])
                if key in seen:
                    continue
                seen.add(key)
                offer = re.split(r"\s[–-]\s", l, maxsplit=1)[-1].strip()
                deals.append({"brand": b["name"], "title": offer[:140], "text": "",
                              "image": imgs[i] if i < len(imgs) else "", "url": b["url"],
                              "type": "kampanje", "date": p["createdAt"]})
                i += 1
    else:
        print("ZERNIO_KEY mangler – hopper over kavalkader")

    out = {"updated": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "deals": deals}
    json.dump(out, open(os.path.join(ROOT, "deals.json"), "w"), ensure_ascii=False, indent=1)
    print(f"{len(deals)} tilbud skrevet")

if __name__ == "__main__":
    main()
