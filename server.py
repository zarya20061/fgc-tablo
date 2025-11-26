import io
from datetime import datetime, timedelta
import os

import requests
from flask import Flask, send_file
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

# ---------- КОНФИГ ----------

OPENWEATHER_KEY = os.environ.get("OPENWEATHER_KEY", "")
# Координаты Sant Cugat (примерно центр)
LAT = 41.472
LON = 2.082

# Размер под PocketBook 632 в горизонтали
W, H = 1448, 1072

# Пути к шрифтам в Linux-контейнере Render
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


# ---------- ПОГОДА ----------

def get_weather():
    """
    Возвращает:
    (temp_now, desc_now, hum_now, wind_now,
     temp_3h, desc_3h,
     temp_6h, desc_6h)
    всё в человекочитаемом виде на русском
    """
    if not OPENWEATHER_KEY:
        # Если ключ не задан — чтоб не падало
        return (18, "ясно", 42, 3,
                17, "ясно",
                15, "ясно")

    # Текущая погода
    url_now = (
        "https://api.openweathermap.org/data/2.5/weather"
        f"?lat={LAT}&lon={LON}&units=metric&lang=ru&appid={OPENWEATHER_KEY}"
    )
    r_now = requests.get(url_now, timeout=5)
    r_now.raise_for_status()
    j_now = r_now.json()

    temp_now = round(j_now["main"]["temp"])
    desc_now = j_now["weather"][0]["description"]
    hum_now = j_now["main"]["humidity"]
    wind_now = j_now["wind"].get("speed", 0)

    # Прогноз (3- и 6-часовой)
    url_fc = (
        "https://api.openweathermap.org/data/2.5/forecast"
        f"?lat={LAT}&lon={LON}&units=metric&lang=ru&appid={OPENWEATHER_KEY}"
    )
    r_fc = requests.get(url_fc, timeout=5)
    r_fc.raise_for_status()
    j_fc = r_fc.json()

    # forecast.list — шаги по 3 часа
    # 0 ~ сейчас+3ч, 1 ~ +6ч
    temp_3h = round(j_fc["list"][0]["main"]["temp"])
    desc_3h = j_fc["list"][0]["weather"][0]["description"]
    temp_6h = round(j_fc["list"][1]["main"]["temp"])
    desc_6h = j_fc["list"][1]["weather"][0]["description"]

    return (temp_now, desc_now, hum_now, wind_now,
            temp_3h, desc_3h,
            temp_6h, desc_6h)


# ---------- ЗАГЛУШКА ПОЕЗДОВ (ПОТОМ ЗАМЕНИМ НА FGC API) ----------

def get_trains():
    """
    Здесь потом будем тянуть реальные поездa FGC.
    Пока: макет на 6 поездов во все направления.
    НО структура уже FGC-стиль: линия, направление, минуты.
    """
    return [
        ("S1", "Barcelona", 3),
        ("S2", "Barcelona", 7),
        ("S6", "Barcelona", 12),
        ("S1", "Terrassa", 5),
        ("S2", "Sabadell", 11),
        ("S7", "Rubí", 15),
    ]


# ---------- РЕНДЕР PNG ПОД ЧИТАЛКУ ----------

def make_tablo_png():
    img = Image.new("L", (W, H), 255)  # L = grayscale, белый фон
    draw = ImageDraw.Draw(img)

    font_title = ImageFont.truetype(FONT_BOLD, 72)
    font_header = ImageFont.truetype(FONT_BOLD, 36)
    font_row = ImageFont.truetype(FONT_REG, 48)
    font_small = ImageFont.truetype(FONT_REG, 32)

    # Заголовок
    draw.text((W // 2, 50), "SANT CUGAT", font=font_title, anchor="mm", fill=0)

    # Шапка таблицы
    draw.line((40, 130, W - 40, 130), fill=0, width=3)
    draw.text((60, 150), "Линия", font=font_header, fill=0)
    draw.text((260, 150), "Направление", font=font_header, fill=0)
    draw.text((W - 60, 150), "Отпр.", font=font_header, anchor="rm", fill=0)
    draw.line((40, 210, W - 40, 210), fill=0, width=3)

    # Строки поездов
    trains = get_trains()
    y = 245
    row_step = 85

    for line_code, dest, mins in trains:
        draw.text((60, y), line_code, font=font_row, fill=0)
        draw.text((260, y), dest, font=font_row, fill=0)
        draw.text((W - 60, y), f"{mins} мин", font=font_row, anchor="rm", fill=0)
        y += row_step

    draw.line((40, y + 10, W - 40, y + 10), fill=0, width=3)

    # Погода: две строки
    (
        temp_now, desc_now, hum_now, wind_now,
        temp_3h, desc_3h,
        temp_6h, desc_6h
    ) = get_weather()

    weather_now = (
        f"Сейчас: {temp_now:+d}°C • {desc_now} • "
        f"влажн. {hum_now}% • ветер {wind_now} м/с"
    )
    weather_fore = (
        f"Прогноз: {temp_3h:+d}°C через 3ч ({desc_3h}), "
        f"{temp_6h:+d}°C через 6ч ({desc_6h})"
    )

    draw.text((60, y + 30), weather_now, font=font_small, fill=0)
    draw.text((60, y + 75), weather_fore, font=font_small, fill=0)

    # Время обновления
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")
    upd = f"Обновлено: {now_str}"
    w_upd, _ = draw.textsize(upd, font=font_small)
    draw.text((W - 60 - w_upd, H - 40), upd, font=font_small, fill=0)

    # В память в PNG
    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    return bio


@app.route("/tablo.png")
def tablo_png():
    bio = make_tablo_png()
    return send_file(bio, mimetype="image/png")


@app.route("/")
def root():
    return "FGC tablo OK. Use /tablo.png"


if __name__ == "__main__":
    # Локальный запуск (если вдруг)
    app.run(host="0.0.0.0", port=8000)
