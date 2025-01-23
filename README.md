# Uptime-Kuma-Report

## Installation
Simply clone and install requirements:
```bash
pip install -r requirements.txt
```

## Usage

There are a number of options available for pulling reports from your Uptime Kuma database, as follows:

- **`-c, --caption TEXT`** - Chart Title **[optional]**

- **`-t, --tag TEXT`** -
  Tag name of the monitors to include in the report **[optional]**

- **`--db PATH`** -
  Path to the Uptime Kuma SQLite database **[required]**

- **`--start TEXT`** -
  Start date in the format `yyyy-mm-dd` **[optional]**

- **`--end TEXT`** -
  End date in the format `yyyy-mm-dd` **[optional]**

- **`-d, --days INTEGER`** -
  Number of days to include in the report **[optional]** (**[required]** if `--start` and `--end` are not provided).

- **`--help`** -
  Display these options.

## Examples

```bash
# Spins up a web server to show the results in a new browser window
python -m kuma-uptime-report --db kuma.db -d 30

# Renders the report to a standalone HTML file
python -m kuma-uptime-report --db kuma.db -d 30 > report.html

# Generates a report spanning the specified dates (if available)
python -m kuma-uptime-report --db kuma.db --start 2024-12-01 --end 2024-12-31 > report.html
```
