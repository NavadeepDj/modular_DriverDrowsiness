# Driver Drowsiness Dashboard

A beautiful, responsive dashboard built with HTML, CSS, and Supabase JavaScript client to visualize driver drowsiness detection data.

## Features

- 🎨 **Bento Grid Layout** - Modern, card-based design
- 📊 **Real-time Statistics** - Total sessions, active sessions, alerts, and metrics
- 📈 **Visual Charts** - State distribution and performance metrics
- 🚨 **Alert Monitoring** - Recent alerts with detailed information
- 📱 **Responsive Design** - Works on desktop, tablet, and mobile
- 🔄 **Auto-refresh** - Updates every 30 seconds automatically

## How to Use

### 1. Generate Config from .env File (Recommended)

The dashboard can automatically use credentials from your `.env` file:

```bash
# Make sure you have a .env file with your Supabase credentials
# SUPABASE_URL=https://xxxxx.supabase.co
# SUPABASE_KEY=your-anon-key-here

# Generate config.js from .env
python generate_config.py
```

This creates a `config.js` file that the dashboard will automatically use.

### 2. Open the Dashboard

Simply open `dashboard.html` in your web browser:
```bash
# Double-click the file or
open dashboard.html
```

The dashboard will automatically connect using credentials from `config.js` (if generated from .env).

### 3. Manual Configuration (Alternative)

If you haven't generated `config.js`, you can manually configure:

1. Enter your Supabase URL (e.g., `https://xxxxx.supabase.co`)
2. Enter your Supabase Anon Key (from Settings > API)
3. Click **Connect**

Your credentials will be saved in browser localStorage for future use.

### 3. View Data

The dashboard will automatically load and display:
- **Statistics Cards**: Total sessions, active sessions, alerts, average drowsiness
- **Recent Sessions**: List of recent driving sessions with metrics
- **Alert Breakdown**: Level 1 vs Level 2 alerts
- **State Distribution**: Visual chart showing driver state distribution
- **Recent Alerts**: Detailed list of recent alert events
- **Performance Metrics**: Max score and average session duration

## Dashboard Sections

### Statistics Cards
- **Total Sessions**: Number of all recorded sessions
- **Active Sessions**: Currently running sessions
- **Total Alerts**: Alerts in the last 24 hours
- **Avg Drowsiness**: Average drowsiness score across all sessions

### Recent Sessions
Shows the 10 most recent sessions with:
- Session ID
- Start time
- Average and maximum drowsiness scores
- Session duration
- Alert counts (Level 1 and Level 2)

### Alert Breakdown
- Level 1 Alerts count
- Level 2 Alerts count

### State Distribution
Visual bar chart showing the distribution of driver states:
- ALERT
- SLIGHTLY_DROWSY
- DROWSY
- VERY_DROWSY
- INATTENTIVE
- NO_FACE

### Recent Alerts
Detailed list of alerts from the last 24 hours showing:
- Alert type (LEVEL1/LEVEL2)
- Timestamp
- Driver state
- Drowsiness score
- PERCLOS percentage
- Trigger reason

### Performance Metrics
- Maximum drowsiness score recorded
- Average session duration

## Auto-Refresh

The dashboard automatically refreshes every 30 seconds to show the latest data. You can also manually refresh by clicking the **Refresh Data** button.

## Styling

The dashboard uses:
- **Bento Grid Layout**: Responsive grid that adapts to screen size
- **Gradient Backgrounds**: Modern purple gradient theme
- **Card-based Design**: Clean, organized information cards
- **Hover Effects**: Interactive elements with smooth transitions
- **Color-coded States**: Visual indicators for different driver states

## Browser Compatibility

Works in all modern browsers:
- Chrome/Edge (recommended)
- Firefox
- Safari
- Opera

## Troubleshooting

### "Failed to connect to Supabase"
- Verify your Supabase URL and Key are correct
- Check that your Supabase project is active
- Ensure RLS policies allow public access (for development)

### "No data available"
- Make sure you've run the driver drowsiness system and it's logging to Supabase
- Check that the database tables exist (run `SUPABASE_SCHEMA.sql`)
- Verify data exists in your Supabase tables

### Dashboard not updating
- Check browser console for errors
- Verify Supabase connection is active
- Try clicking "Refresh Data" manually

## Security Note

The dashboard uses the Supabase **anon key** (public key), which is safe for client-side use. However, make sure your RLS (Row Level Security) policies are properly configured in production.

For development, you can use public access policies, but in production, implement proper authentication.

## Customization

You can customize the dashboard by:
- Modifying colors in the `<style>` section
- Adjusting grid layout in `.bento-grid`
- Changing refresh interval (currently 30 seconds)
- Adding new cards or sections
- Modifying data queries

## Next Steps

1. **Real-time Updates**: Use Supabase Realtime subscriptions for live updates
2. **Charts**: Add more advanced charts using Chart.js or D3.js
3. **Filters**: Add date range filters and session filtering
4. **Export**: Add data export functionality (CSV, PDF)
5. **Alerts**: Add browser notifications for new alerts

