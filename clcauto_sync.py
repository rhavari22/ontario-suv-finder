"""Import qualifying public CLCAuto listings into the website inventory.
Only confirmed Ontario listings with CAD prices, images and listing links are published.
"""
import json,urllib.request,urllib.parse,datetime,re
from pathlib import Path
BASE="https://www.clcauto.com/api/v1/cars"
def val(v):
    return str(v.get("value","") if isinstance(v,dict) else (v or "")).lower()
def parse(v):
    if not isinstance(v,dict): return None
    currency=str(v.get("currency","")).upper()
    loc=" ".join(str(v.get(k) or "") for k in ("location","city","province","state","region","address"))
    if not re.search(r"\\b(?:Ontario|ON)\\b",loc,re.I) or currency!="CAD":return None
    try:
        price=float(v["price"]);km=float(v["mileage"])*(1 if str(v.get("mileage_unit","mi")).lower()=="km" else 1.609344)
    except (KeyError,ValueError,TypeError):return None
    if not (0<price<35000 and 0<=km<90000):return None
    fuel=val(v.get("fuel_type") or v.get("fuelType"))
    transmission=val(v.get("transmission"))
    body=val(v.get("body_type") or v.get("bodyStyle") or v.get("bodyType"))
    if fuel not in ("gasoline","gas","hybrid") or transmission not in ("automatic","cvt","dct","amt"):return None
    if not any(t in body for t in ("suv","crossover","sport utility")) and not re.search(r"suv|crossover",str(v.get("title","")),re.I):return None
    images=v.get("images") or []
    image=images[0] if isinstance(images,list) and images else v.get("image_url") or v.get("imageUrl") or ""
    if isinstance(image,dict):image=image.get("url","")
    url=v.get("url") or v.get("listing_url") or v.get("listingUrl") or ""
    if not str(url).startswith("https://") or not str(image).startswith("https://"):return None
    return {"brand":v.get("make",""),"model":v.get("model",""),"year":v.get("year"),"price":price,
            "mileageKm":round(km),"fuel":fuel,"condition":"used","transmission":transmission,
            "bodyType":body,"province":"Ontario","imageUrl":image,"url":url,"source":"CLCAuto"}
items=[];cursor=None
for page in range(10):
    params={"limit":"100","lang":"en","sort":"newest"}
    if cursor:params["cursor"]=cursor
    req=urllib.request.Request(BASE+"?"+urllib.parse.urlencode(params),headers={"Accept":"application/json","User-Agent":"OntarioSUVFinder/1.0"})
    with urllib.request.urlopen(req,timeout=35) as res: payload=json.load(res)
    batch=payload if isinstance(payload,list) else (payload.get("cars") or payload.get("listings") or payload.get("items") or payload.get("data",{}).get("cars") or [])
    if not isinstance(batch,list):raise RuntimeError("Unexpected CLCAuto response format")
    items.extend(batch)
    cursor=payload.get("next_cursor") if isinstance(payload,dict) else None
    if not cursor:break
vehicles={}
for v in items:
    x=parse(v)
    if x:vehicles[x["url"]]=x
# Do not wipe a previously valid inventory if an upstream source changes unexpectedly.
out={"updatedAt":datetime.datetime.now(datetime.timezone.utc).isoformat(),"listings":list(vehicles.values())}
Path("listings.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("CLCAuto pages checked, records scanned, eligible:",page+1,len(items),len(vehicles))
