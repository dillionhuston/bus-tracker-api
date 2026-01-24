# initdb.py
import json
from datetime import datetime

from app.models.Database import Base, engine, SessionLocal
from app.models.Route import Route, Stop, RouteStop

db = SessionLocal()

try:
    print("Dropping and recreating tables...")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    # 1. Load stops from geojson
    print("Loading stops from geojson...")
    with open("app/data/stops.geojson", "r", encoding="utf-8") as f:
        geo = json.load(f)

    stop_count = 0
    for feature in geo["features"]:
        p = feature["properties"]
        g = feature["geometry"]
        coords = g["coordinates"]
        atco = p["AtcoCode"]
        if not atco or not atco.startswith("7000"):
            continue

        name = p.get("CommonName", "Unnamed stop").strip()
        if name in ("0", ""):
            name = "Unnamed stop"

        try:
            lat = float(p.get("Latitude") or coords[1])
            lon = float(p.get("Longitude") or coords[0])
        except:
            lat = lon = None

        db.add(Stop(id=atco, name=name, latitude=lat, longitude=lon))
        stop_count += 1

    db.commit()
    print(f"→ Inserted {stop_count:,} stops\n")

    # 2. Parse Metro.cif
    print("Parsing Metro.cif...")
    with open("app/data/Metro.cif", "r", encoding="utf-8", errors="replace") as f:
        lines = [line.rstrip("\n") for line in f if line.strip() and not line.startswith("#")]

    routes = {}
    route_sequences = {}
    current_key = None
    current_stops = []
    current_direction_char = None

    def save_current_sequence():
        if current_key is None or len(current_stops) < 3:
            return
        existing = route_sequences.get(current_key, [])
        if len(current_stops) > len(existing):
            route_sequences[current_key] = current_stops[:]
            print(f"Saved/updated sequence for {current_key:12} → {len(current_stops)} stops")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if line.startswith("QDN"):
            save_current_sequence()
            parts = line.split(maxsplit=3)
            if len(parts) < 4:
                continue
            _, route_code, dir_char, description = parts
            current_direction_char = dir_char
            current_stops = []
            temp_key = f"{route_code}-{dir_char}"
            routes[temp_key] = {
                "code": route_code,
                "dir_char": dir_char,
                "direction": "Outbound" if dir_char == "O" else "Inbound",
                "name": f"{route_code} {description.strip()}",
            }
            current_key = temp_key

        elif line.startswith("QSN") and current_key:
            save_current_sequence()
            parts = line.split()
            variant_code = None
            for idx in range(4, min(9, len(parts))):
                p = parts[idx].strip("X")
                if len(p) >= 1 and any(c.isdigit() for c in p) and p[0] not in ('2','0','1'):
                    variant_code = p
                    break
            if not variant_code:
                for p in parts[3:]:
                    p = p.strip("X")
                    if len(p) >= 1 and p[0].isdigit():
                        variant_code = p
                        break
            if not variant_code and "code" in routes.get(current_key, {}):
                variant_code = routes[current_key]["code"]
            variant_code = variant_code or "UNKNOWN"
            final_key = f"{variant_code}-{current_direction_char}"
            if final_key != current_key and current_key in routes:
                if final_key not in routes:
                    routes[final_key] = routes.pop(current_key)
            current_key = final_key
            current_stops = []

        elif line.startswith(("QO", "QI", "QT")) and current_key:
            stop_id = line[2:14].strip()
            if stop_id.startswith("7000") and len(stop_id) == 12:
                current_stops.append(stop_id)

    save_current_sequence()

    # Cleanup invalid keys
    to_remove = [k for k in route_sequences if not k or k.endswith("-") or "--" in k or k.count("-") < 1]
    for bad in to_remove:
        print(f"Removing invalid key: {bad}")
        route_sequences.pop(bad, None)
        routes.pop(bad, None)

    # Normalize keys
    normalized_routes = {}
    normalized_sequences = {}
    for old_key, seq in route_sequences.items():
        if old_key not in routes:
            continue
        meta = routes[old_key]
        code = meta.get("code")
        if not code or code == "UNKNOWN":
            possible = old_key.split("-")[0]
            if any(c.isdigit() for c in possible) or len(possible) in (1,2,3):
                code = possible
            else:
                continue
        dir_char = meta.get("dir_char")
        if not dir_char or dir_char not in ("O", "I"):
            parts = old_key.split("-")
            if len(parts) >= 2:
                last = parts[-1].strip()
                if last and last[0] in ("O", "I"):
                    dir_char = last[0]
                else:
                    dir_char = "O"
            else:
                dir_char = "O"
        new_key = f"{code}-{dir_char}"
        if new_key not in normalized_sequences or len(seq) > len(normalized_sequences[new_key]):
            normalized_sequences[new_key] = seq
            normalized_routes[new_key] = meta

    routes = normalized_routes
    route_sequences = normalized_sequences

    print(f"\nAfter normalization: {len(routes)} routes / {len(route_sequences)} sequences\n")

        # 3. Insert into database – FINAL VERSION WITH PER-ROUTE DEDUPLICATION
    print("Inserting routes and links (deduplicating stops per route)...")

    inserted_routes = 0
    inserted_links = 0
    skipped_duplicates = 0
    skipped_intra_route = 0

    # Phase 1: Insert all Routes
    for key in list(routes.keys()):
        if db.query(Route).filter(Route.id == key).first():
            continue
        meta = routes[key]
        route = Route(
            id=key,
            name=meta.get("name", f"Route {key}"),
            direction=meta.get("direction", "Outbound" if key.endswith("-O") else "Inbound"),
            official_timetable=None,
            timetable_last_updated=datetime.utcnow()
        )
        db.add(route)
        inserted_routes += 1

    db.commit()  # Commit routes first
    print(f"→ Committed {inserted_routes} routes\n")

    # Phase 2: Insert RouteStops with deduplication
    for key, seq in route_sequences.items():
        if key not in routes:
            continue

        # Existing stops in DB for this route
        existing_in_db = {
            row[0] for row in db.query(RouteStop.stop_id)
                                .filter(RouteStop.route_id == key)
                                .all()
        }

        # Track stops we've seen in THIS sequence (prevent intra-route duplicates)
        seen_in_this_seq = set()

        new_links = []

        for idx, stop_id in enumerate(seq, start=1):
            # Skip if already in DB
            if stop_id in existing_in_db:
                skipped_duplicates += 1
                continue

            # Skip if already seen in this sequence (prevents duplicate in same route)
            if stop_id in seen_in_this_seq:
                skipped_intra_route += 1
                continue

            seen_in_this_seq.add(stop_id)

            # Safety check: stop must exist
            if db.query(Stop).filter(Stop.id == stop_id).scalar() is None:
                print(f"Warning: stop {stop_id} not found → skipping in {key}")
                continue

            new_links.append(RouteStop(
                route_id=key,
                stop_id=stop_id,
                sequence=idx,
                direction=key[-1]
            ))

        if new_links:
            db.bulk_save_objects(new_links)
            inserted_links += len(new_links)

    db.commit()

    print("\n" + "═" * 80)
    print("DATABASE POPULATED – SUCCESS")
    print(f"  Routes added:           {inserted_routes}")
    print(f"  Links added:            {inserted_links:,}")
    print(f"  Duplicates from DB skipped: {skipped_duplicates:,}")
    print(f"  Duplicates within route skipped: {skipped_intra_route:,}")
    print("═" * 80 + "\n")

    print("Start your API:")
    print("  uvicorn main:app --reload")
    print("\nQuick tests:")
    print("  http://127.0.0.1:8000/route/1A-O/stops")
    print("  http://127.0.0.1:8000/route/2F-O/stops")
    print("  http://127.0.0.1:8000/route/N12-O/stops")
    print("  http://127.0.0.1:8000/route/7H-I/stops")

except Exception as e:
    db.rollback()
    print("Error:")
    print(str(e))
    raise
finally:
    db.close()