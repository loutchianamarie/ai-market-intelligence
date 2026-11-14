import sys, re, html, json, hashlib, urllib.request, datetime
from html.parser import HTMLParser
URLS = {
 "cj_pkg_index": "https://bradleyboehmke.github.io/completejourney/index.html",
 "cj_coupon_redemptions": "https://bradleyboehmke.github.io/completejourney/reference/coupon_redemptions.html",
 "cj_campaigns": "https://bradleyboehmke.github.io/completejourney/reference/campaigns.html",
 "cj_transactions": "https://bradleyboehmke.github.io/completejourney/reference/transactions.html",
 "cj_py_port_readme": "https://raw.githubusercontent.com/cunningjames/completejourney_py/main/README.md",
 "google_ai_features": "https://developers.google.com/search/docs/appearance/ai-features",
 "kroger_digital_coupons": "https://www.kroger.com/pr/weekly-digital-deals",
 "walmart_coupons": "https://www.walmart.com/cp/coupons/1229796",
 "target_circle": "https://www.target.com/circle",
 "aldi_about": "https://www.aldi.us/about-us/",
 "ftc_ai_claims": "https://www.ftc.gov/business-guidance/blog/2023/02/keep-your-ai-claims-check",
}
class T(HTMLParser):
    def __init__(s): super().__init__(); s.out=[]; s.skip=0
    def handle_starttag(s,t,a):
        if t in ("script","style","noscript","svg"): s.skip+=1
    def handle_endtag(s,t):
        if t in ("script","style","noscript","svg") and s.skip: s.skip-=1
    def handle_data(s,d):
        if not s.skip and d.strip(): s.out.append(d.strip())
res = {}
for k,u in URLS.items():
    try:
        req = urllib.request.Request(u, headers={"User-Agent":"Mozilla/5.0 (course research)", "Accept-Language":"en-US"})
        raw = urllib.request.urlopen(req, timeout=25).read().decode("utf8","ignore")
        if u.endswith(".md"): text = raw
        else:
            p=T(); p.feed(raw); text="\n".join(p.out)
        text = re.sub(r"\n{2,}","\n",text)
        open(f"data/sources/_cache/{k}.txt","w",encoding="utf8").write(text)
        res[k] = {"url":u,"chars":len(text),"ok":True,"retrieved_at":datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),"sha16":hashlib.sha256(text.encode()).hexdigest()[:16]}
    except Exception as e:
        res[k] = {"url":u,"ok":False,"error":str(e)[:120]}
json.dump(res, open("data/sources/_cache/fetch_log.json","w"), indent=1)
for k,v in res.items(): print(k, v.get("ok"), v.get("chars", v.get("error")))
