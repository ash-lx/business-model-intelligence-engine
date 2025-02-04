# Advanced Sitemap Scraper

A powerful, asynchronous web scraping tool built with Python that automatically fetches and processes XML sitemaps, crawls URLs in parallel, and saves structured content. This tool is designed for efficient, large-scale web scraping while being respectful of rate limits.

## Features

- **Automatic Sitemap Discovery**: Automatically finds and parses XML sitemaps from any website
- **Parallel Processing**: Crawls multiple URLs simultaneously using async batching
- **Configurable Settings**: Easily adjust crawling behavior through a central config file
- **Rate Limiting**: Built-in rate limiting to prevent overwhelming target servers
- **Robust Error Handling**: Automatic retries and comprehensive error logging
- **Structured Output**: Saves crawled content in organized JSON files
- **Performance Monitoring**: Tracks execution time and success rates

## Requirements

- Python 3.7+
- Required packages:
  ```
  crawl4ai
  ultimate-sitemap-parser
  aiofiles
  ```

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. Install dependencies:
   ```bash
   pip install crawl4ai ultimate-sitemap-parser aiofiles
   ```

## Configuration

All settings can be configured in `config.py`:

### Website Configuration
```python
WEBSITE_URL = "https://example.com"  # Target website
OUTPUT_DIR = "scraped_data"          # Directory for saved data
```

### Crawling Settings
```python
BATCH_SIZE = 10                # URLs to process in parallel
RATE_LIMIT = 2                # Seconds between requests
MAX_CONCURRENT_REQUESTS = 5    # Maximum concurrent requests
```

### File Settings
```python
SITEMAP_OUTPUT = "sitemap.xml"  # Output sitemap filename
SUMMARY_FILE = "summary.json"   # Summary file name
```

### Retry Settings
```python
MAX_RETRIES = 3    # Maximum retry attempts
RETRY_DELAY = 5    # Seconds between retries
```

### Additional Settings
```python
LOG_LEVEL = "INFO"  # Logging level
CRAWL_TIMEOUT = 30  # Request timeout in seconds
USER_AGENT = "..."  # Custom user agent
```

## Usage

1. Configure settings in `config.py` according to your needs.

2. Run the scraper:
   ```bash
   python sitemap_scrapper.py
   ```

3. The script will:
   - Fetch the sitemap from the configured website
   - Save the sitemap as XML
   - Crawl all URLs in parallel batches
   - Save content to JSON files in the output directory
   - Generate a summary file

## Output Structure

### Sitemap XML
```xml
<?xml version='1.0' encoding='utf-8'?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://example.com/page1</loc>
    </url>
    ...
</urlset>
```

### Content JSON
Each crawled URL is saved as a JSON file containing:
```json
{
    "url": "https://example.com/page1",
    "lastmod": "2024-01-23",
    "priority": "0.8",
    "content": "Page content...",
    "html": "Raw HTML...",
    "crawl_time": "2024-01-23T12:00:00"
}
```

### Summary JSON
```json
{
    "total_urls": 100,
    "successful_crawls": 98,
    "crawl_time": "2024-01-23T12:00:00",
    "urls": [...]
}
```

## Performance Optimization

To optimize crawling speed:

1. Increase `BATCH_SIZE` for more parallel processing
2. Reduce `RATE_LIMIT` if the target server allows
3. Increase `MAX_CONCURRENT_REQUESTS` for more concurrent connections

Note: Be mindful of the target server's capacity and robots.txt rules when adjusting these settings.

## Error Handling

The scraper includes robust error handling:

- Automatic retries for failed requests
- Rate limit respect
- Timeout handling
- Comprehensive logging
- Graceful failure recovery

## Logging

Logs are output with timestamp and level:
```
2024-01-23 12:00:00 - INFO - Starting scrape of website: example.com
2024-01-23 12:00:01 - INFO - Found 100 URLs in sitemap
2024-01-23 12:00:02 - INFO - Successfully crawled: /page1
...
```

## Contributing

Feel free to submit issues, fork the repository, and create pull requests for any improvements.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
