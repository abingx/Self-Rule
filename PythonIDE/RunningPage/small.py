import widget
from widget import show, family, SMALL, MEDIUM, LARGE, CIRCULAR, RECTANGULAR, INLINE
import requests
import json
from datetime import datetime, timedelta
import time

# ── 工具函数 ──────────────────────────────────────────────────────

def parse_date(str_date):
    if isinstance(str_date, datetime):
        return str_date
    if isinstance(str_date, (int, float)):
        return datetime.fromtimestamp(str_date)
    if not isinstance(str_date, str) or not str_date.strip():
        return datetime.min
    try:
        return datetime.fromisoformat(str_date.replace(" ", "T"))
    except:
        return datetime.min

def normalize_run_data(run):
    if not run or not isinstance(run, dict):
        return None
    start_date = parse_date(run.get('start_date_local'))
    start_timestamp = start_date.timestamp() if start_date != datetime.min else float('nan')
    distance_meters = float(run.get('distance', 0)) or 0
    distance_km = distance_meters / 1000
    moving_seconds = parse_time_to_seconds(run.get('moving_time') or run.get('elapsed_time') or 0)
    return {
        **run,
        '_startDate': start_date,
        '_startTimestamp': start_timestamp,
        '_distanceMeters': distance_meters,
        '_distanceKm': distance_km,
        '_movingSeconds': moving_seconds
    }

def parse_time_to_seconds(time_str):
    if isinstance(time_str, (int, float)):
        return time_str
    if not isinstance(time_str, str):
        return 0
    parts = time_str.split(':')
    if len(parts) != 3:
        return 0
    hours = int(parts[0]) if parts[0].isdigit() else 0
    minutes = int(parts[1]) if parts[1].isdigit() else 0
    seconds = float(parts[2]) if parts[2] else 0
    return hours * 3600 + minutes * 60 + seconds

def start_of_day(d):
    return d.replace(hour=0, minute=0, second=0, microsecond=0)

def start_of_week(d):
    day = d.weekday()  # Monday=0
    if day != 0:
        d = d - timedelta(days=day)
    return start_of_day(d)

def start_of_month(d):
    return d.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

def start_of_year(d):
    return d.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

def summarize(runs, since):
    filtered_runs = [r for r in runs if r and r.get('_startTimestamp', float('nan')) >= since.timestamp()]
    count = len(filtered_runs)
    distance = sum(r.get('_distanceKm', float(r.get('distance', 0)) / 1000) for r in filtered_runs)
    total_time = sum(r.get('_movingSeconds', parse_time_to_seconds(r.get('moving_time') or r.get('elapsed_time') or 0)) for r in filtered_runs)
    return {
        'count': count,
        'distance': f"{distance:.2f}",
        'duration': format_duration(total_time),
        'pace': format_pace(total_time / distance) if distance > 0 else None,
        'maxDistance': f"{max((r.get('_distanceKm', float(r.get('distance', 0)) / 1000) for r in filtered_runs), default=0):.2f}",
        'bestPace': None  # 简化实现
    }

def format_duration(seconds):
    if not isinstance(seconds, (int, float)) or not (seconds > 0):
        return None
    total_seconds = round(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes}:{secs:02d}"

def format_pace(seconds_per_km):
    if not isinstance(seconds_per_km, (int, float)) or not (seconds_per_km > 0):
        return None
    total_seconds = round(seconds_per_km)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes}'{seconds:02d}\""

# ── 获取和处理数据 ────────────────────────────────────────────────

DATA_URL = "https://raw.githubusercontent.com/abingx/running_page/master/src/static/activities.json"

def get_data():
    try:
        response = requests.get(DATA_URL, timeout=10)
        response.raise_for_status()
        return response.json()
    except:
        return []

def sanitize_data(data):
    if not isinstance(data, list):
        return []
    return [normalize_run_data(item) for item in data if item and isinstance(item, dict) and item.get('type') == 'Run']

def process_data(runs):
    now = datetime.now()
    runs = sorted(runs, key=lambda r: r.get('_startTimestamp', float('-inf')), reverse=True)
    today = summarize(runs, start_of_day(now))
    week = summarize(runs, start_of_week(now))
    month = summarize(runs, start_of_month(now))
    year = summarize(runs, start_of_year(now))
    return today, week, month, year

# ── 主逻辑 ────────────────────────────────────────────────────────

if family == SMALL:
    data = get_data()
    runs = sanitize_data(data)
    today, week, month, year = process_data(runs)
    
    today_distance = today['distance']
    today_date = datetime.now().strftime("%Y/%m/%d")
    
    show(
        title="Running Page",
        value=today_distance,
        subtitle=today_date,
        color="#4ECDC4",
        icon="",
        rows=[
            {"label": "Week", "value": week['distance']},
            {"label": "Month", "value": month['distance']},
            {"label": "Year", "value": year['distance']},
        ]
    )