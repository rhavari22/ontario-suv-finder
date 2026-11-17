"""Refresh Ontario SUV listings from an authorized HTTPS JSON feed."""
import os,json,datetime,urllib.request
from pathlib import Path
url=os.getenv("INVENTORY_FEED_URL","").strip()
if not url:
    print("No authorized inventory feed configured; leaving listings unchanged.")
    raise SystemExit(0)
if not url.startswith("https://"): raise SystemExit("Feed must use HTTPS")
headers={"Accept":"application/json","User-Agent":"OntarioSUVFinder/1.0"}
if os.getenv("INVENTORY_FEED_TOKEN"): headers["Authorization"]="Bearer "+os.environ["INVENTORY_FEED_TOKEN"]
with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=45) as response: payload=json.load(response)
items=payload if isinstance(payload,list) else payload.get("listings",payload.get("vehicles",payload.get("results",[])))
if not isinstance(items,list): raise SystemExit("Invalid feed format")
def eligible(v):
    try:
        price=float(v["price"]); km=float(v.get("mileageKm",0))
        body=str(v.get("bodyType",v.get("body_type",""))).lower()
        fuel=str(v.get("fuel",v.get("fuelType",""))).lower()
        transmission=str(v.get("transmission","")).lower()
        condition=str(v.get("condition","")).lower()
        province=str(v.get("province",v.get("region",""))).lower()
        return (body in ("suv","crossover") and 0<=price<35000 and condition in ("new","used")
                and (condition=="new" or 0<=km<90000) and province in ("on","ontario")
                and (fuel in ("gas","gasoline","petrol","hybrid","regular hybrid","mild hybrid")
                     or ("hybrid" in fuel and "plug" not in fuel and "phev" not in fuel))
                and ("automatic" in transmission or transmission in ("cvt","e-cvt")))
    except (KeyError,ValueError,TypeError): return False
result={"updatedAt":datetime.datetime.now(datetime.timezone.utc).isoformat(),"listings":[v for v in items if isinstance(v,dict) and eligible(v)]}
Path("listings.json").write_text(json.dumps(result,ensure_ascii=False)+"\n",encoding="utf-8")
print("Eligible SUVs:",len(result["listings"]))
