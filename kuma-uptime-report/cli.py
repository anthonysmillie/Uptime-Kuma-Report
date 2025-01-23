import click
import sys
from datetime import datetime, timedelta
from .database import Database
from .chart import chart_plotly


@click.command(help="""
Generates a report using the Uptime Kuma database and displays it via a web interface.
To save the report as a standalone HTML, redirect stdout to a file.

You can specify both --start and --end dates to define a custom date range,
or alternatively use --days to generate a report for the last X days.
""")
@click.option('--caption', '-c', help='Optional chart title.', type=str, default="Uptime Report")
@click.option('--tag', '-t', help='Tag name of the monitors to include in the report.', type=str, default=None)
@click.option('--db', help='Path to the Uptime Kuma SQLite database.', type=click.Path(exists=True), required=True)
@click.option('--start', help='Start date in the format yyyy-mm-dd.', type=str)
@click.option('--end', help='End date in the format yyyy-mm-dd.', type=str)
@click.option('--days', '-d', help='Number of days to include in the report (if --start and --end are not provided).',
              type=int)
def cli(db: str, start: str, end: str, days: int, tag: str, caption: str):
    """
    Command-line interface to generate uptime reports from Uptime Kuma database.
    """
    # Validate and parse input dates
    start_date = None
    end_date = None

    if start and end:
        # Validate date format for --start and --end
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d").replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = datetime.strptime(end, "%Y-%m-%d").replace(hour=23, minute=59, second=59, microsecond=999999)
        except ValueError:
            click.echo("Error: Invalid date format. Use yyyy-mm-dd for --start and --end.", err=True)
            sys.exit(1)

        # Ensure start date is before end date
        if start_date >= end_date:
            click.echo("Error: Start date must be before end date.", err=True)
            sys.exit(1)
    elif days:
        if days <= 0:
            click.echo("Error: Number of days must be greater than zero.", err=True)
            sys.exit(1)
        end_date = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
        start_date = end_date - timedelta(days=days)
    else:
        click.echo("Error: You must provide either --start and --end or --days.", err=True)
        sys.exit(1)

    # Initialize Database connection
    try:
        Database(db)  # Initializes and sets Database.db singleton
    except RuntimeError as e:
        click.echo(f"Error connecting to database: {e}", err=True)
        sys.exit(1)

    try:
        # Generate chart
        chart = chart_plotly(start=start_date, end=end_date, tagname=tag, caption=caption)

        if sys.stdout.isatty():  # Show interactive chart if run in terminal
            chart.show()
        else:  # Redirect output to save the chart as a standalone HTML file
            print(chart.to_html(include_plotlyjs='cdn'))

    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()