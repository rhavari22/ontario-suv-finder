"""Fetch public Dealersway inventory for explicitly configured Ontario dealers.
No dealer slugs are bundled until a real Ontario dealer endpoint is verified.
"""
import json, os, re, urllib.request, urllib.parse, datetime
from pathlib import Path

CONFIG=Path("dealersway_dealers.json")
dealers=json.loads(CONFIG.read_text(encoding="utf-8"))
if not isinstance(dealers,list): raise SystemExit("Dealer config must be a JSON array")
if not dealers:
    print("No verified Ontario Dealersway dealer slugs configured; leaving inventory unchanged.")
    raise SystemExit(0)

def fetch(dealer):
    slug=dealer["slug"]
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,79}",slug): raise ValueError("Invalid dealer slug")
    # Dealersway caps the public API at 100 per page.
    all_items=[]
    for offset in range(0,10000,100):
        params=urllib.parse.urlencode({"priceMax":34999,"limit":100,"offset":offset})
        url=f"https://api.dealersway.com/v1/dealers/{slug}/inventory/vehicles?{params}"
        request=urllib.request.Request(url,headers={"Accept":"application/json","User-Agent":"OntarioSUVFinder/1.0"})
        with urllib.request.urlopen(request,timeout=40) as response:
            batch=json.load(response)
        if not isinstance(batch,list): raise ValueError("Unexpected API response")
        all_items.extend(batch)
        if len(batch)<100: break
    return all_items

def normalize(v,d):
    if not isinstance(v,dict) or str(v.get("status","")).lower()!="available": return None
    try: price=float(v["price"])
    except (ValueError,TypeError,KeyError): return None
    if not 0<price<35000: return None
    body=str(v.get("bodyStyle","")).strip().lower()
    if body not in ("suv","crossover","sport utility vehicle"): return None
    trans=str(v.get("transmission","")).lower()
    if not any(t in trans for t in ("automatic","cvt","e-cvt")): return None
    fuel=str(v.get("fuelType","")).lower().strip()
    if any(x in fuel for x in ("plug-in","plug in","phev","electric","ev","diesel")): return None
    if fuel not in ("gas","gasoline","petrol","hybrid","regular hybrid","mild hybrid","hev"): return None
    condition=str(v.get("inventoryType") or v.get("condition") or "").lower()
    if condition not in ("new","used"): return None
    try: mileage=float(v["mileage"])
    except (ValueError,TypeError,KeyError): return None if condition=="used" else None
    unit=str(v.get("mileageUnit","km")).lower()
    km=mileage*1.609344 if unit in ("mi","mile","miles") else mileage
    if condition=="used" and not 0<=km<90000: return None
    images=v.get("images") or []
    image=images[min(max(int(v.get("primaryImageIndex") or 0),0),len(images)-1)] if images else ""
    # Listing URLs must be supplied/verified by the dealer. Do not invent a storefront route.
    link=v.get("listingUrl") or v.get("url") or d.get("inventoryUrl","")
    if link and not str(link).startswith("https://"): link=""
    return {"brand":v.get("make",""),"make":v.get("make",""),"model":v.get("model",""),
            "year":v.get("year"),"price":price,"mileageKm":round(km),"fuel":fuel,
            "condition":condition,"transmission":trans,"bodyType":body,
            "province":"Ontario","imageUrl":image,"url":link,
            "vin":v.get("vin"),"source":"Dealersway","dealer":d.get("name",d["slug"])}

vehicles={}
for dealer in dealers:
    if str(dealer.get("province","")).lower() not in ("on","ontario"):
        raise SystemExit("Only Ontario dealerships are supported")
    try:
        batch=fetch(dealer)
    except Exception as exc:
        raise SystemExit(f"Dealersway request failed for {dealer['slug']}: {type(exc).__name__}: {exc}") from exc
    for item in batch:
        vehicle=normalize(item,dealer)
        if vehicle:
            key=vehicle.get("vin") or (dealer["slug"]+":"+str(item.get("id") or item.get("slug")))
            vehicles[key]=vehicle
result={"updatedAt":datetime.datetime.now(datetime.timezone.utc).isoformat(),"listings":list(vehicles.values())}
Path("listings.json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(f"Published {len(vehicles)} qualifying vehicles from {len(dealers)} dealers")
