# FGC Sant Cugat Centre Schedule Image Generator

This repository contains a Python script and GitHub Actions workflow that automatically generates a PNG image every minute with the upcoming Ferrocarrils de la Generalitat de Catalunya (FGC) train schedule for **Sant Cugat Centre** station.

## How It Works
The data is fetched primarily from the FGC **GTFS-Realtime** feed. If the real-time API is unavailable, the script falls back to a static timetable (lines S1 and S2 with 5-minute intervals during peak hours and 10-minute intervals off-peak, using realistic schedule assumptions). The image is generated using Pillow and updated on the repository's **gh-pages** branch, which is served via GitHub Pages.

## Image Details
The generated image (`fgc_sant_cugat.png`) is **1072×1448 px** with a white background and black text. It includes:
- **Title**: "FGC Sant Cugat Centre" (bold, 60 pt).
- **Current Time** (in Europe/Madrid local time, format `30.11 17:25`, 45 pt).
- **Upcoming trains**: 6 next departures:
  - Left side shows line and destination (e.g. "S1 → Barcelona", "S2 → Sabadell").
  - Right side shows time until departure (e.g. "2 min", "Сейчас!" for "Now!", "17 min") in bold 55 pt. All text fits within the image with appropriate margins and spacing.

Text is rendered with DejaVu Sans fonts to support Russian text (e.g. "Сейчас!").

## Setup Instructions
1. **Clone or upload files**: Add all files from this repository (including `generate.py`, the workflow YAML, etc.) to a new GitHub repository.
2. **GitHub Pages**: In your repository settings, enable GitHub Pages to serve from the **gh-pages** branch (the workflow will create/update this branch automatically).
3. **Install Dependencies**: The GitHub Actions workflow will install Python dependencies listed in `requirements.txt` (Pillow, requests, pytz, etc.).
4. **Workflow Schedule**: The included GitHub Actions workflow (`.github/workflows/update_image.yml`) is scheduled to run **every minute** (`cron: */1 * * * *`). It will:
   - Checkout the repository and install dependencies.
   - Run `generate.py` to fetch data and create the image.
   - Commit and push the updated `fgc_sant_cugat.png` to the `gh-pages` branch.
5. **Access the Image**: Once the workflow runs, the image will be available at:
