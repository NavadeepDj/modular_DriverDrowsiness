# Quick Start: Dashboard with .env

## Setup Dashboard in 2 Steps

### Step 1: Generate Config from .env

```bash
cd modular_DriverDrowsiness/modular
python generate_config.py
```

This reads your `.env` file and creates `config.js` for the dashboard.

### Step 2: Open Dashboard

Simply open `dashboard.html` in your browser - it will automatically connect using credentials from `config.js`!

```bash
# Double-click dashboard.html or
start dashboard.html  # Windows
open dashboard.html   # Mac
xdg-open dashboard.html  # Linux
```

## That's It! 🎉

The dashboard will:
- ✅ Automatically load credentials from `config.js` (generated from `.env`)
- ✅ Connect to Supabase automatically
- ✅ Start displaying your data immediately
- ✅ Auto-refresh every 30 seconds

## Regenerating Config

If you update your `.env` file, just run:
```bash
python generate_config.py
```

## Manual Configuration

If you prefer not to use `.env`, you can:
1. Enter credentials manually in the dashboard
2. They'll be saved in browser localStorage

## Troubleshooting

**Dashboard shows "config.js not found"**
- Run `python generate_config.py` first

**"Failed to connect to Supabase"**
- Check your `.env` file has correct `SUPABASE_URL` and `SUPABASE_KEY`
- Regenerate config: `python generate_config.py`

**No data showing**
- Make sure you've run the driver drowsiness system and it's logging to Supabase
- Check that database tables exist (run `SUPABASE_SCHEMA.sql`)

