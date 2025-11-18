# Debugging Guide - Golden Source Address Issue

## Problem
Getting error: "No Golden Source address provided" when trying to push updates, even though a Golden Source address was found.

## Changes Made to Help Debug

### 1. Frontend Validation (`templates/index.html`)

#### Added Validation Before Attaching Event Listener (Lines 335-349)
```javascript
const hasValidAddress = data.matched_address && 
    Object.keys(data.matched_address).length > 0 &&
    (data.matched_address.address1 || data.matched_address.state);

if (hasValidAddress) {
    // Attach event listener
} else {
    // Disable button and show error
    pushUpdatesBtn.disabled = true;
    pushUpdatesBtn.title = "No valid Golden Source address available";
}
```

**What This Does:**
- Checks that `matched_address` exists
- Verifies it's not an empty object
- Ensures it has at least `address1` or `state` field

If validation fails, the button will be disabled with a tooltip explaining why.

#### Added Console Logging (Lines 116-120, 367-382)

**When Match Response is Received:**
```javascript
console.log('Match Response Data:');
console.log('  Match found:', data.match_found);
console.log('  Matched address:', data.matched_address);
console.log('  Pinellas matches:', data.pinellas_matches);
```

**When Push Updates Button is Clicked:**
```javascript
console.log('Push Updates - Data being sent:');
console.log('  Pinellas Matches:', pinellas_matches);
console.log('  Golden Source Address:', golden_source_address);
console.log('Request payload:', JSON.stringify(requestData, null, 2));
```

### 2. Backend Debug Logging (`web_app.py`)

#### Added Debug Output (Lines 109-114)
```python
print(f"\n[Push Updates Request Debug]")
print(f"  Request data keys: {list(data.keys())}")
print(f"  Pinellas matches count: {len(pinellas_matches)}")
print(f"  Golden source address keys: {list(golden_source_address.keys())}")
print(f"  Golden source address: {golden_source_address}")
```

#### Improved Error Message (Lines 122-128)
```python
if not golden_source_address or len(golden_source_address) == 0:
    error_msg = f'No Golden Source address provided. Received: {golden_source_address}'
    print(f"  ERROR: {error_msg}")
    return jsonify({'success': False, 'error': error_msg}), 400
```

## How to Debug

### Step 1: Open Browser Console
1. Open your browser's Developer Tools (F12)
2. Go to the Console tab
3. Clear any existing messages

### Step 2: Search for an Address
Enter an address and click "Search For Your Address"

### Step 3: Check Console Output

Look for this output:
```
Match Response Data:
  Match found: true
  Matched address: {address1: "...", address2: "...", ...}
  Pinellas matches: [{...}, {...}]
```

**Check:**
- ✅ Is `Match found` = `true`?
- ✅ Is `Matched address` an object with fields?
- ✅ Does `Matched address` have `address1`, `state`, etc.?
- ✅ Is `Pinellas matches` an array with items?

### Step 4: Check Button State

**If Button is Disabled:**
- Hover over the "Push Updates" button
- Check the tooltip - it should say why it's disabled
- This means the frontend validation failed

**If Button is Enabled:**
- The frontend validation passed
- The Golden Source address should be valid

### Step 5: Click Push Updates

When you click the button, check the console for:
```
Push Updates - Data being sent:
  Pinellas Matches: [...]
  Golden Source Address: {...}
Request payload: {...}
```

**Verify:**
- ✅ `Golden Source Address` is not empty
- ✅ It contains the expected fields (address1, state, etc.)

### Step 6: Check Backend Logs

In your Python/Flask console, look for:
```
[Push Updates Request Debug]
  Request data keys: ['pinellas_matches', 'golden_source_address']
  Pinellas matches count: 2
  Golden source address keys: ['address1', 'address2', 'Mailing City', 'state', 'zipcode']
  Golden source address: {'address1': '...', ...}
```

## Common Issues and Solutions

### Issue 1: `matched_address` is Empty or Undefined

**Symptoms:**
- Button is disabled
- Console shows: `Matched address: undefined` or `Matched address: {}`

**Cause:**
- The Claude API response didn't include a matched address
- The address matching failed

**Solution:**
Check the backend logs to see if the match was actually successful. The issue might be in the `address_agent.py` or how Claude's response is parsed.

### Issue 2: `matched_address` Missing Required Fields

**Symptoms:**
- Button is disabled
- Console shows object but without `address1` or `state`

**Cause:**
- The Golden Source table doesn't have the expected column names
- The data is stored in different fields

**Solution:**
1. Check your Golden Source table schema
2. Verify column names match: `address1`, `address2`, `Mailing City`, `state`, `zipcode`
3. If different, update the field mappings in the code

### Issue 3: Data Lost in Transit

**Symptoms:**
- Frontend shows valid data in console
- Backend receives empty object

**Cause:**
- JSON serialization issue
- Network/CORS problem

**Solution:**
1. Check the "Request payload" in frontend console
2. Compare with "Golden source address" in backend logs
3. Check browser Network tab for the actual request body

### Issue 4: Golden Source Address Not Being Retrieved

**Symptoms:**
- Match is found but `matched_address` is empty from the start

**Cause:**
- The `/match` endpoint isn't properly returning the Golden Source data

**Solution:**
Check `web_app.py` lines 72-74:
```python
if response_data['match_found']:
    matched_address = claude_response.get('matched_address', {})
    response_data['matched_address'] = matched_address
```

Verify that `claude_response` actually contains the matched address data.

## Testing Checklist

- [ ] Open browser console (F12)
- [ ] Clear console
- [ ] Search for an address
- [ ] Check "Match Response Data" output
- [ ] Verify `matched_address` has data
- [ ] Check if "Push Updates" button is enabled or disabled
- [ ] If enabled, click it
- [ ] Check "Push Updates - Data being sent" output
- [ ] Check backend Python console for debug output
- [ ] If error occurs, note the exact error message
- [ ] Take screenshots of both frontend and backend logs

## Next Steps

After running through these debugging steps, you should see exactly where the Golden Source address data is getting lost or not being populated. Share the console output (both browser and backend) to identify the root cause.

