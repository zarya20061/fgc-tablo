import requests
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timezone
import pytz
import math

# Configuration
STATION_STOP_ID = "70037"
DATA_URL = "https://fgc.opendatasoft.com/api/records/1.0/search/?dataset=trip-updates-gtfs_realtime&refine.stop_id=" + STATION_STOP_ID
TIMEZONE = pytz.timezone("Europe/Madrid")
IMAGE_WIDTH = 1072
IMAGE_HEIGHT = 1448
OUTPUT_FILE = "fgc_sant_cugat.png"

# Font paths (adjust if needed for your system)
FONT_TITLE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_TEXT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_TEXT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def fetch_realtime_updates():
    try:
        resp = requests.get(DATA_URL, timeout=5)
        if resp.status_code != 200:
            return None
        data = resp.json()
    except Exception:
        return None

    records = data.get("records")
    if not records:
        return None

    events = []
    now_utc = datetime.now(timezone.utc)
    now_ts = now_utc.timestamp()

    for rec in records:
        fields = rec.get("fields", {})
        line = fields.get("route_short_name") or fields.get("route_id")
        trip_headsign = fields.get("trip_headsign", "")
        trip_id = fields.get("trip_id", "")

        if not line:
            if "Terrassa" in trip_headsign:
                line = "S1"
            elif "Sabadell" in trip_headsign:
                line = "S2"
            elif "Barcelona" in trip_headsign or "Catalunya" in trip_headsign:
                line = "S2" if "S2" in trip_id else "S1"

        arr_time, dep_time = None, None
        for i in range(50):
            if fields.get(f"stop_id{i}") == STATION_STOP_ID:
                arr_time = fields.get(f"arrival_time{i}")
                dep_time = fields.get(f"departure_time{i}")
                break

        arr_time = arr_time or fields.get("arrival_time")
        dep_time = dep_time or fields.get("departure_time")

        if not arr_time and not dep_time:
            continue

        pred_time = arr_time or dep_time
        try:
            from dateutil import parser
            dt = parser.isoparse(pred_time)
            dt = dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            pred_ts = dt.timestamp()
        except Exception:
            try:
                pred_ts = float(pred_time)
                if pred_ts > 1e12:
                    pred_ts /= 1000.0
            except Exception:
                continue

        diff_sec = pred_ts - now_ts
        if diff_sec < -30:
            continue
        time_str = "Сейчас!" if diff_sec < 60 else f"{int(diff_sec // 60)} мин"

        if "Terrassa" in trip_headsign:
            direction = "Terrassa"
        elif "Sabadell" in trip_headsign:
            direction = "Sabadell"
        else:
            direction = "Barcelona"

        events.append((pred_ts, line, direction, time_str))

    events.sort()
    return [(l, d, t) for _, l, d, t in events[:6]]

def get_static_schedule_events(now_local):
    weekday = now_local.weekday()
    hour_minute = now_local.hour * 60 + now_local.minute

    if weekday < 5 and ((450 <= hour_minute < 570) or (1020 <= hour_minute < 1200)):
        interval = 5
        offsets = {'S1→Barcelona': 2, 'S2→Barcelona': 0, 'S1→Terrassa': 1, 'S2→Sabadell': 3}
    elif weekday < 5:
        interval = 10
        offsets = {'S1→Barcelona': 5, 'S2→Barcelona': 0, 'S1→Terrassa': 7, 'S2→Sabadell': 2}
    else:
        interval = 20
        offsets = {'S1→Barcelona': 10, 'S2→Barcelona': 0, 'S1→Terrassa': 12, 'S2→Sabadell': 2}

    now_min = now_local.hour * 60 + now_local.minute
    sec = now_local.second
    threshold = 30
    events = []

    for key, off in offsets.items():
        base = (now_min // interval) * interval + off
        if now_min % interval == off and sec >= threshold:
            base += interval
        elif base < now_min:
            base += interval
        for j in range(3):
            t_min = base + j * interval
            if t_min >= 1440:
                continue
            diff = t_min - now_min
            time_str = "Сейчас!" if diff < 1 else f"{diff} мин"
            line, direction = key.split("→")
            events.append((diff, line.strip(), direction.strip(), time_str))

    events.sort()
    return [(l, d, t) for _, l, d, t in events[:6]]

def draw_schedule_image(events, now_local):
    img = Image.new('RGB', (IMAGE_WIDTH, IMAGE_HEIGHT), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    font_title = ImageFont.truetype(FONT_TITLE, 60)
    font_time = ImageFont.truetype(FONT_TEXT, 45)
    font_left = ImageFont.truetype(FONT_TEXT, 55)
    font_right = ImageFont.truetype(FONT_TEXT_BOLD, 55)

    # Title
    title_text = "FGC Sant Cugat Centre"
    bbox = draw.textbbox((0, 0), title_text, font=font_title)
    title_w = bbox[2] - bbox[0]
    title_h = bbox[3] - bbox[1]
    draw.text(((IMAGE_WIDTH - title_w) // 2, 50), title_text, font=font_title, fill="black")

    # Current time
    time_text = now_local.strftime("%d.%m %H:%M")
    bbox = draw.textbbox((0, 0), time_text, font=font_time)
    time_w = bbox[2] - bbox[0]
    time_h = bbox[3] - bbox[1]
    time_y = 50 + title_h + 10
    draw.text(((IMAGE_WIDTH - time_w) // 2, time_y), time_text, font=font_time, fill="black")

    # Train entries
    y = time_y + time_h + 30
    for line, dest, t_str in events:
        left = f"{line} → {dest}"
        right = t_str

        bbox_left = draw.textbbox((0, 0), left, font=font_left)
        left_h = bbox_left[3] - bbox_left[1]

        bbox_right = draw.textbbox((0, 0), right, font=font_right)
        right_w = bbox_right[2] - bbox_right[0]
        right_h = bbox_right[3] - bbox_right[1]

        draw.text((50, y), left, font=font_left, fill="black")
        draw.text((IMAGE_WIDTH - 50 - right_w, y), right, font=font_right, fill="black")

        y += max(left_h, right_h) + 30

    img.save(OUTPUT_FILE)

def main():
    now_local = datetime.now(TIMEZONE)
    events = fetch_realtime_updates() or get_static_schedule_events(now_local)
    draw_schedule_image(events, now_local)

if __name__ == "__main__":
    main()
