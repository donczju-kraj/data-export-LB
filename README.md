# Luigi's Box Catalog Export

A Python script to export all items from a Luigi's Box catalog to a CSV file using the Content Export API.

## Overview

This tool connects to the Luigi's Box Content Export API, authenticates using HMAC-SHA256, and exports all catalog items to a CSV file. The export includes all object attributes and handles pagination automatically.

## Prerequisites

- Python 3.9 or higher
- Luigi's Box account with API access
- Tracker ID (public key) and API key (private key) from Luigi's Box

## Installation

1. Clone this repository:

```bash
git clone <repository-url>
cd data-export-LB
```

2. Create a virtual environment (recommended):

```bash
python3 -m venv .venv
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate  # On Windows
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

1. Create a `.env` file in the project root:

```bash
cp .env.example .env  # if example exists
# or create manually
touch .env
```

2. Add your Luigi's Box credentials to `.env`:

```env
TRACKER_ID='your-tracker-id-here'
API_KEY='your-api-key-here'
```

**Important:** Never commit the `.env` file to version control. It contains sensitive credentials.

3. (Optional) Customize export settings in [main.py](main.py):
   - `HIT_FIELDS`: Specify which fields to return (empty list returns all fields)
   - `REQUESTED_TYPES`: Filter by content types (empty list returns all types except "query")
   - `PAGE_SIZE`: Number of items per API request (max 500)

## Usage

Run the export script:

```bash
python main.py
```

The script will:

1. Load credentials from `.env`
2. Connect to Luigi's Box API with HMAC authentication
3. Fetch all catalog items (handling pagination automatically)
4. Export data to `catalog/luigisbox_catalog_export.csv`

## Output

The exported CSV file contains:

- `url`: Item URL
- `type`: Content type
- `exact`: Exact match flag
- Dynamic columns for all attributes found in your catalog
- `nested`: JSON representation of nested data structures

The output file is saved to: `catalog/luigisbox_catalog_export.csv`

## API Documentation

- [Content Export API](https://docs.luigisbox.com/indexing/api/v1/export.html)
- [HMAC Authentication](https://docs.luigisbox.com/api_principles.html#authentication)

## Troubleshooting

### FileNotFoundError

If you get a file not found error, ensure the `catalog/` directory exists. The script should create it automatically, but you can create it manually:

```bash
mkdir -p catalog
```

### Authentication Errors

- Verify your `TRACKER_ID` and `API_KEY` in the `.env` file
- Ensure there are no extra quotes or spaces
- Check that your API key has the necessary permissions in Luigi's Box

### Missing Dependencies

If you encounter import errors, reinstall dependencies:

```bash
pip install -r requirements.txt
```

## Security Notes

- The `.env` file is excluded from version control via `.gitignore`
- Never commit API keys or sensitive credentials to your repository
- Keep your `API_KEY` confidential and rotate it regularly
