# Election Scheduling Timezone Fix - Documentation

## Problem Summary

Users in IST (Indian Standard Time, UTC+5:30) were experiencing incorrect scheduling times for elections. When a user entered a time in the UI (e.g., 2:00 PM IST), the system was storing and displaying a different time.

## Root Cause Analysis

The bug was caused by **double timezone conversion** - once in JavaScript and once in the backend:

### JavaScript Bug (admin.html, schedule.html)
```javascript
// OLD (WRONG) CODE:
const utc = new Date(d.getTime() - d.getTimezoneOffset()*60000);
hidden.value = utc.toISOString();
```

For IST users:
- `getTimezoneOffset()` returns `-330` (IST is 330 minutes ahead of UTC)
- The code did: `d.getTime() - (-330)*60000` = `d.getTime() + 19800000`
- This **added** 5.5 hours instead of converting to UTC!
- Example: Input 14:00 IST → Sent 19:30 UTC (WRONG! Should be 08:30 UTC)

### Backend Bug (app.py)
```python
# OLD (WRONG) CODE:
utc_dt = dt - timedelta(minutes=tz_offset)
```

The backend was trying to convert again, even though JavaScript already sent UTC values (albeit wrong ones). This caused **double conversion**.

## Solution

### JavaScript Fix
```javascript
// NEW (CORRECT) CODE:
hidden.value = d.toISOString();
```

**Why this works:**
- `new Date("2025-01-15T14:00")` creates a Date object in the browser's **local timezone**
- `.toISOString()` automatically converts to UTC - no manual calculation needed!
- For IST: Input "14:00" → Automatically converts to "08:30 UTC" ✓

### Backend Fix
```python
# NEW (CORRECT) CODE:
if start_time_utc and end_time_utc:
    # UTC values are already correct from JavaScript - use directly
    start_time = start_time_utc.replace('Z', '+00:00')
    end_time = end_time_utc.replace('Z', '+00:00')
else:
    # Fallback: convert from local using offset
    utc_dt = dt + timedelta(minutes=tz_offset)  # Changed from minus to plus
```

**Why this works:**
- If JavaScript sends `_utc` fields (when offset ≠ 0), use them directly
- If not (when offset = 0, i.e., UTC timezone), do conversion with correct formula
- For IST: `offset = -330`, so `UTC = local + (-330)` = `local - 330 minutes` ✓

## Changes Made

### 1. templates/admin.html
- Fixed JavaScript timezone conversion logic
- Added debug console.log statements
- Shows all form data before submission

### 2. templates/schedule.html
- Same JavaScript fixes as admin.html
- Consistent behavior across both forms

### 3. app.py
- Fixed `/schedule_election` route to use UTC values directly
- Fixed `/schedule` route similarly
- Added comprehensive debug logging to server console
- Added session storage of last scheduled election details
- Added flash messages showing scheduled times in IST

### 4. templates/admin.html (display)
- Added "Last Scheduled Election Debug Info" box
- Shows: Browser input, TZ offset, UTC submitted, UTC stored, IST computed
- Helps users verify the fix visually

## Test Results

### Test 1: IST User
- **Input:** 2025-11-01 14:00 (2:00 PM IST)
- **Expected UTC:** 2025-11-01 08:30 (8:30 AM UTC)
- **Stored UTC:** 2025-11-01T08:30:00+00:00 ✓
- **Displayed:** 01 Nov 2025, 02:00 PM IST ✓

### Test 2: UTC User
- **Input:** 2025-11-02 10:00 (10:00 AM UTC)
- **Expected UTC:** 2025-11-02 10:00 (10:00 AM UTC)
- **Stored UTC:** 2025-11-02T10:00:00+00:00 ✓
- **Displayed:** 02 Nov 2025, 03:30 PM IST ✓

## Verification Steps for Users

1. **Schedule an election** with your desired IST time
2. **Check the debug box** at the top of the admin dashboard:
   - Verify "Browser Input (Local)" shows what you entered
   - Verify "IST Computed (Display)" shows the expected time
3. **Check the "Upcoming" section** - time should match your intended schedule
4. **Check the flash message** at the top - it shows the scheduled time in IST

## Debug Output Example

**Server Console:**
```
[DEBUG SCHEDULE] Raw form data:
  start_time (local): 2025-10-20T14:00
  start_time_utc: 2025-10-20T08:30:00.000Z
  end_time (local): 2025-10-20T16:00
  end_time_utc: 2025-10-20T10:30:00.000Z
  tz_offset: -330 minutes
[DEBUG SCHEDULE] Using UTC values directly
[DEBUG SCHEDULE] Final UTC values:
  start_time: 2025-10-20T08:30:00.000+00:00
  end_time: 2025-10-20T10:30:00.000+00:00
```

**Browser Console:**
```
[DEBUG] Timezone offset set to: -330 minutes (negative = ahead of UTC)
[DEBUG] Converting local time: 2025-10-20T14:00
[DEBUG] Browser local time: Sat Oct 20 2025 14:00:00 GMT+0530 (India Standard Time)
[DEBUG] UTC time: 2025-10-20T08:30:00.000Z
[DEBUG] Form submission data:
   start_time = 2025-10-20T14:00
   start_time_utc = 2025-10-20T08:30:00.000Z
   tz_offset = -330
```

## Technical Notes

### Understanding JavaScript getTimezoneOffset()
- Returns **minutes from UTC to local time** (UTC - local)
- For IST (UTC+5:30): returns **-330** (negative because IST is ahead)
- For PST (UTC-8:00): returns **+480** (positive because PST is behind)
- **Don't use it for manual conversion** - use `.toISOString()` instead!

### Understanding datetime-local Input
- Always represents **local time** in the browser's timezone
- When parsed by JavaScript: `new Date("2025-01-15T14:00")` uses local timezone
- No 'Z' suffix = local time; with 'Z' suffix = UTC time

### IST Filter (istfmt)
Already existed in the codebase and works correctly:
```python
@app.template_filter("istfmt")
def istfmt(value):
    dt = parse_iso(value)
    dt = to_ist(dt)
    return dt.strftime("%d %b %Y, %I:%M %p IST")
```

## Future Improvements

1. **Client-side timezone detection:** Show user's detected timezone in the UI
2. **Timezone selector:** Allow users to select their timezone explicitly
3. **More comprehensive tests:** Add automated browser tests with different timezones
4. **Remove debug box:** Once verified by users, the debug box can be hidden or removed
