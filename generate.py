import requests
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timezone, timedelta
import pytz
import math

# Configuration
STATION_STOP_ID = "70037"
DATA_URL = "https://fgc.opendatasoft.com/api/records/1.0/search/?dataset=trip-updates-gtfs_realtime&refine.stop_id=" + STATION_STOP_ID
TIMEZONE = pytz.timezone("Europe/Madrid")
IMAGE_WIDTH = 1072
IMAGE_HEIGHT = 1448
OUTPUT_FILE = "fgc_sant_cugat.png"

# Font paths (assuming DejaVu fonts available on system)
FONT_TITLE = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_TEXT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_TEXT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

def fetch_realtime_updates():
    """Fetch GTFS realtime data and return list of events (line, direction, time_str) or None if API fails."""
    try:
        resp = requests.get(DATA_URL, timeout=5)
        if resp.status_code != 200:
            return None
        data = resp.json()
    except Exception as e:
        return None
    records = data.get("records")
    if not records:
        return None
    events = []
    now_utc = datetime.now(timezone.utc)
    now_ts = now_utc.timestamp()
    for rec in records:
        fields = rec.get("fields", {})
        # Determine route short name (S1, S2) if possible
        line = None
        if "route_short_name" in fields:
            line = fields["route_short_name"]
        elif "route_id" in fields:
            # route_id might be numeric or string like "S1"
            rid = fields["route_id"]
            if isinstance(rid, str) and rid.startswith("S"):
                line = rid
        if line is None:
            # try derive from trip_headsign or trip_id
            trip_headsign = fields.get("trip_headsign", "")
            if "Terrassa" in trip_headsign:
                line = "S1"
            elif "Sabadell" in trip_headsign:
                line = "S2"
            elif "Barcelona" in trip_headsign or "Catalunya" in trip_headsign:
                # cannot distinguish directly, use other info if available
                trip_id = fields.get("trip_id", "")
                if "S2" in trip_id:
                    line = "S2"
                else:
                    line = "S1"
        # Determine arrival time for this stop
        arr_time = None
        dep_time = None
        # Search indexed fields for this stop
        for i in range(0, 50):
            key = f"stop_id{i}"
            if key in fields and str(fields[key]) == STATION_STOP_ID:
                if f"arrival_time{i}" in fields:
                    arr_time = fields[f"arrival_time{i}"]
                if f"departure_time{i}" in fields:
                    dep_time = fields[f"departure_time{i}"]
                break
        # If not found by index, check top-level (if only one stop per record)
        if arr_time is None and dep_time is None:
            if "arrival_time" in fields or "departure_time" in fields:
                arr_time = fields.get("arrival_time")
                dep_time = fields.get("departure_time")
        if arr_time is None and dep_time is None:
            continue
        # Use arrival_time if available, else departure_time
        pred_time = arr_time if arr_time is not None else dep_time
        # Convert to epoch seconds
        if isinstance(pred_time, str):
            try:
                from dateutil import parser
                dt = parser.isoparse(pred_time)
                if dt.tzinfo:
                    dt = dt.astimezone(timezone.utc)
                else:
                    dt = dt.replace(tzinfo=timezone.utc)
                pred_ts = dt.timestamp()
            except Exception:
                try:
                    pred_ts = float(pred_time)
                except Exception:
                    continue
        else:
            pred_ts = float(pred_time)
            # If it's likely milliseconds, convert to seconds
            if pred_ts > 1e12:
                pred_ts = pred_ts / 1000.0
        diff_sec = pred_ts - now_ts
        if diff_sec < -30:
            continue  # already departed
        if diff_sec < 60:
            time_str = "Сейчас!"
        else:
            diff_min = math.floor(diff_sec / 60)
            time_str = f"{int(diff_min)} min"
        # Determine direction (destination)
        direction = None
        trip_headsign = fields.get("trip_headsign", "")
        if trip_headsign:
            if "Terrassa" in trip_headsign:
                direction = "Terrassa"
            elif "Sabadell" in trip_headsign:
                direction = "Sabadell"
            elif "Barcelona" in trip_headsign or "Catalunya" in trip_headsign:
                direction = "Barcelona"
        if direction is None:
            # If not deduced from headsign, use line and known mapping:
            if line == "S1":
                if "Terrassa" in trip_headsign:
                    direction = "Terrassa"
                else:
                    direction = "Barcelona"
            elif line == "S2":
                if "Sabadell" in trip_headsign:
                    direction = "Sabadell"
                else:
                    direction = "Barcelona"
            else:
                direction = "Barcelona"
        events.append((pred_ts, line, direction, time_str))
    events.sort(key=lambda x: x[0])
    events = events[:6]
    output_events = [(line, direction, time_str) for (_ts, line, direction, time_str) in events]
    return output_events

def get_static_schedule_events(now_local):
    """Generate next 6 events from static schedule if realtime not available."""
    weekday = now_local.weekday()
    hour_minute = now_local.hour * 60 + now_local.minute
    if weekday < 5:
        # Weekday
        if (7*60+30) <= hour_minute < (9*60+30) or (17*60) <= hour_minute < (20*60):
            branch_interval = 5  # peak hours
            offsets = {'S2_inbound': 0, 'S1_inbound': 2, 'S1_outbound': 1, 'S2_outbound': 3}
        else:
            branch_interval = 10  # off-peak weekday
            offsets = {'S2_inbound': 0, 'S1_inbound': 5, 'S2_outbound': 2, 'S1_outbound': 7}
    else:
        # Weekend (Sat/Sun)
        branch_interval = 20
        offsets = {'S2_inbound': 0, 'S1_inbound': 10, 'S2_outbound': 2, 'S1_outbound': 12}
    now_min = now_local.hour * 60 + now_local.minute
    sec = now_local.second
    events = []
    threshold = 30
    for flow, off in offsets.items():
        interval = branch_interval
        base = (now_min // interval) * interval + off
        if base < now_min:
            base += interval
        if now_min % interval == off:
            if sec < threshold:
                base = now_min
            else:
                base += interval
        for j in range(3):
            t_min = base + j * interval
            if t_min >= 24*60:
                break  # stop at end of day
            diff = t_min - now_min
            if diff < 0:
                diff += 24*60
            if diff < 0:
                continue
            if diff < 1:
                time_str = "Сейчас!"
            else:
                time_str = f"{diff} min"
            parts = flow.split('_')
            line = parts[0]  # e.g. "S1"
            direction = "Barcelona" if parts[1] == "inbound" else ("Terrassa" if line == "S1" else "Sabadell")
            events.append((diff, line, direction, time_str))
    events.sort(key=lambda x: x[0])
    events = events[:6]
    output_events = [(line, direction, time_str) for (_diff, line, direction, time_str) in events]
    return output_events

def draw_schedule_image(events, now_local):
    img = Image.new('RGB', (IMAGE_WIDTH, IMAGE_HEIGHT), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    font_title = ImageFont.truetype(FONT_TITLE, 60)
    font_time = ImageFont.truetype(FONT_TEXT, 45)
    font_left = ImageFont.truetype(FONT_TEXT, 55)
    font_right = ImageFont.truetype(FONT_TEXT_BOLD, 55)
    # Title
    title_text = "FGC Sant Cugat Centre"
    title_w, title_h = draw.textsize(title_text, font=font_title)
    title_x = (IMAGE_WIDTH - title_w) // 2
    title_y = 50
    draw.text((title_x, title_y), title_text, font=font_title, fill="black")
    # Current time
    time_str = now_local.strftime("%d.%m %H:%M")
    time_w, time_h = draw.textsize(time_str, font=font_time)
    time_x = (IMAGE_WIDTH - time_w) // 2
    time_y = title_y + title_h + 10
    draw.text((time_x, time_y), time_str, font=font_time, fill="black")
    # Train list
    list_y = time_y + time_h + 30
    margin_left = 50
    margin_right = 50
    line_gap = 30
    for line, direction, t_str in events:
        left_text = f"{line} \u2192 {direction}"
        right_text = t_str
        left_w, left_h = draw.textsize(left_text, font=font_left)
        right_w, right_h = draw.textsize(right_text, font=font_right)
        draw.text((margin_left, list_y), left_text, font=font_left, fill="black")
        right_x = IMAGE_WIDTH - margin_right - right_w
        draw.text((right_x, list_y), right_text, font=font_right, fill="black")
        list_y += max(left_h, right_h) + line_gap
    img.save(OUTPUT_FILE)

def main():
    now_local = datetime.now(TIMEZONE)
    events = fetch_realtime_updates()
    if events is None or len(events) == 0:
        events = get_static_schedule_events(now_local)
    events = events[:6]
    draw_schedule_image(events, now_local)

if __name__ == "__main__":
    main()
