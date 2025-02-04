"""Configuration settings for the sitemap scraper."""

# Website configuration
WEBSITE_URL = "https://www.sistrix.com/api/"
OUTPUT_DIR = "scraped_data"

# Crawling settings
BATCH_SIZE = 10  # Number of URLs to process in parallel
RATE_LIMIT = 2  # Seconds between requests
MAX_CONCURRENT_REQUESTS = 5  # Maximum number of concurrent requests

# File settings
SITEMAP_OUTPUT = "sitemap.xml"  # Name of the output sitemap file
SUMMARY_FILE = "summary.json"  # Name of the summary file

# Retry settings
MAX_RETRIES = 3  # Maximum number of retries for failed requests
RETRY_DELAY = 5  # Seconds to wait between retries

# Logging settings
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

# Crawl4AI settings
CRAWL_TIMEOUT = 30  # Seconds before timing out a request
USER_AGENT = "Mozilla/5.0 (compatible; SitemapScraper/1.0)"
