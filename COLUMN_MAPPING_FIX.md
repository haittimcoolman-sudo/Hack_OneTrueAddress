# Column Mapping Fix - Resolving "column does not exist" Error

## Problem
After successfully passing the Golden Source address to the backend, we encountered this error when trying to insert into the `internal_updates` table:

```
Error pushing to internal updates: column "address1" of relation "internal_updates" does not exist
LINE 1: ..., "Exclusion", "ID", "Media", "State", "Zipcode", "address1"...
```

## Root Cause

The issue was a **column name mismatch** between different tables:

1. **Golden Source Table** columns:
   - `address1` (lowercase)
   - `address2` (lowercase)
   - `Mailing City`
   - `state` (lowercase)
   - `zipcode` (lowercase)

2. **Internal/Pinellas Table** columns (as shown in error):
   - `Address` (capitalized, no "1" suffix)
   - `State` (capitalized)
   - `Zipcode` (capitalized)
   - `City` (or similar variation)

3. **internal_updates Table**: Has the same column structure as the Internal/Pinellas table

### The Problem
When we tried to apply Golden Source address fields to the consolidated record, the code was **adding new columns** with Golden Source names (like `address1`) instead of **updating existing columns** with Internal names (like `Address`).

When the INSERT statement was generated, it included these mismatched column names, causing the database error.

## Solution

### 1. Only Update Existing Columns (Don't Add New Ones)

**Before:**
```python
if matching_col:
    consolidated_record[matching_col] = field_value
else:
    # This was the problem - adding new columns
    consolidated_record[field_name] = field_value  ❌
```

**After:**
```python
if matching_col:
    consolidated_record[matching_col] = field_value
else:
    # Don't add new columns - only update existing ones
    print(f"⚠️  Warning: No matching column found for '{field_name}' - skipping")  ✅
```

### 2. Improved Column Matching with Flexible Patterns

Added support for multiple naming variations to match columns more reliably:

```python
field_patterns = {
    'address1': [
        'address1', 'address_1', 'address 1', 
        'address',  # Match "Address" (no suffix)
        'street', 'street address', 'street_address'
    ],
    'address2': [
        'address2', 'address_2', 'address 2', 
        'address line 2', 'address_line_2'
    ],
    'state': ['state', 'st'],
    'zipcode': [
        'zipcode', 'zip_code', 'zip code', 'zip', 
        'postal', 'postalcode', 'postal_code'
    ]
}
```

### 3. Normalized Comparison Logic

The matching logic now:
- Converts both column names and patterns to lowercase
- Replaces underscores with spaces
- Strips extra whitespace
- Compares normalized values

```python
for col_name in consolidated_record.keys():
    col_lower = col_name.lower().replace('_', ' ').strip()
    for pattern in patterns:
        pattern_normalized = pattern.lower().replace('_', ' ').strip()
        if col_lower == pattern_normalized:
            matching_col = col_name
            break
```

This allows matching:
- `Address` ↔ `address` ↔ `address1`
- `State` ↔ `state`
- `Zipcode` ↔ `zipcode` ↔ `zip_code`
- `City` ↔ `Mailing City` (through existing city field detection)

### 4. Added Detailed Warning Messages

When a column cannot be matched, the system now shows:
```
⚠️  Warning: No matching column found for 'address1' (value: '10 Village LN') - skipping
   Available columns: ['Address', 'City', 'State', 'Zipcode', 'Media', 'Exclusion', 'ID']
```

This helps diagnose column name mismatches quickly.

## How It Works Now

### Example Flow

1. **Golden Source Address:**
   ```json
   {
     "address1": "10 Village LN",
     "address2": "",
     "Mailing City": "Safety Harbor",
     "state": "FL",
     "zipcode": "34695"
   }
   ```

2. **Internal Record (from Pinellas table):**
   ```json
   {
     "Address": "10 Village Dr",
     "City": "Safety Harbor",
     "State": "FL",
     "Zipcode": "34695",
     "Media": "Fiber",
     "Active Customer": "Y",
     "Exclusion": "N"
   }
   ```

3. **Column Matching Process:**
   - `address1` ("10 Village LN") → matches `Address` → updates to "10 Village LN"
   - `address2` ("") → no match found in Internal record → skipped
   - `state` ("FL") → matches `State` → updates to "FL"
   - `zipcode` ("34695") → matches `Zipcode` → updates to "34695"
   - `Mailing City` ("Safety Harbor") → matches `City` → updates to "Safety Harbor"

4. **Final Consolidated Record:**
   ```json
   {
     "Address": "10 Village LN",      ← Updated from Golden Source
     "City": "Safety Harbor",          ← Updated from Golden Source
     "State": "FL",                    ← Updated from Golden Source
     "Zipcode": "34695",               ← Updated from Golden Source
     "Media": "Fiber",                 ← Preserved from Internal record
     "Active Customer": "Y",           ← Preserved from Internal record
     "Exclusion": "N"                  ← Preserved from Internal record
   }
   ```

5. **INSERT Statement:**
   ```sql
   INSERT INTO "team_cool_and_gang"."internal_updates" 
   ("Address", "City", "State", "Zipcode", "Media", "Active Customer", "Exclusion") 
   VALUES ('10 Village LN', 'Safety Harbor', 'FL', '34695', 'Fiber', 'Y', 'N')
   ```
   ✅ All column names exist in the table!

## Benefits

1. **No More Column Mismatch Errors**: Only existing columns are used
2. **Flexible Matching**: Handles various naming conventions
3. **Better Debugging**: Clear warnings show which fields couldn't be matched
4. **Preserves Data Integrity**: Non-address fields remain unchanged
5. **Golden Source Priority**: Address data comes from the trusted source

## Testing

When you run the application now:

1. Search for an address
2. Click "Push Updates to Internal Database"
3. **Check the console output** for column mapping results:
   ```
   [Single Record - Applying Golden Source Address]
     Updated Address: '10 Village Dr' -> '10 Village LN'
     Updated City: 'Safety Habor' -> 'Safety Harbor'
     Updated State: 'FL' -> 'FL'
     Updated Zipcode: '34695' -> '34695'
     ✓ Applied Golden Source address to single record
   ```

4. If any fields can't be matched, you'll see:
   ```
   ⚠️  Warning: No matching column found for 'address2' (value: 'Apt 5') - skipping
      Available columns: ['Address', 'City', 'State', 'Zipcode', 'Media']
   ```

5. The INSERT should now succeed without column errors

## Files Modified

- `golden_source.py` (lines 593-625, 774-806)
  - Updated `consolidate_pinellas_records()` method
  - Improved column matching logic
  - Added flexible pattern matching
  - Removed logic that added new columns
  - Enhanced debugging output

## What If My Table Has Different Column Names?

If your internal table uses completely different column names (e.g., `StreetAddress` instead of `Address`), you can add them to the patterns:

```python
field_patterns = {
    'address1': [
        'address1', 'address', 'street', 
        'streetaddress', 'street address',  # Add your variations here
        'addr', 'addr1'
    ],
    # ... etc
}
```

The system will show warnings for unmatched fields, making it easy to identify which patterns need to be added.

