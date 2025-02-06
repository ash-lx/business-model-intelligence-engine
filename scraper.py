import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
import aiofiles
import xml.etree.ElementTree as ET
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.content_filter_strategy import PruningContentFilter
from usp.tree import sitemap_tree_for_homepage

# Default configuration


class Config:
    OUTPUT_DIR = "scraped_data"
    BATCH_SIZE = 10
    RATE_LIMIT = 2
    MAX_CONCURRENT_REQUESTS = 5
    LOG_LEVEL = "INFO"
    LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"


try:
    import config
except ImportError:
    config = Config

# Set up logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format=config.LOG_FORMAT
)


class SitemapScraper:
    def __init__(self, output_dir: str = config.OUTPUT_DIR):
        self.output_dir = Path(output_dir)
        self.raw_dir = self.output_dir / 'raw'
        self.markdown_dir = self.output_dir / 'markdown'

        # Create necessary directories
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.markdown_dir.mkdir(parents=True, exist_ok=True)

        self.rate_limit = config.RATE_LIMIT
        self.last_request_time = 0

        # Configure browser settings
        self.browser_config = BrowserConfig(
            browser_type="chromium",
            headless=True,
            viewport_width=1280,
            viewport_height=720,
            verbose=True
        )

        # Configure markdown generation
        self.markdown_generator = DefaultMarkdownGenerator(
            content_filter=PruningContentFilter(
                threshold=0.48,  # Adjust based on content quality needed
                threshold_type="fixed",
                min_word_threshold=10
            ),
            options={
                "ignore_links": False,
                "escape_html": True,
                "body_width": 80
            }
        )

    async def fetch_sitemap(self, url: str) -> List[Dict[str, Any]]:
        """Fetch and parse the sitemap from the website."""
        try:
            # First try to get URLs from sitemap
            tree = sitemap_tree_for_homepage(url)
            urls = []
            for page in tree.all_pages():
                url_data = {
                    'loc': page.url,
                    'lastmod': None,
                    'priority': None
                }
                urls.append(url_data)

            # If no URLs found in sitemap, fall back to the homepage
            if not urls:
                logging.info("No URLs found in sitemap, using homepage URL")
                urls = [{
                    'loc': url,
                    'lastmod': None,
                    'priority': None
                }]

            logging.info(f"Found {len(urls)} URLs to analyze")
            return urls

        except Exception as e:
            logging.error(f"Error parsing sitemap: {
                          e}, falling back to homepage URL")
            return [{
                'loc': url,
                'lastmod': None,
                'priority': None
            }]

    async def crawl_single_url(self, url: str, url_data: Dict[str, Any], crawler: AsyncWebCrawler) -> Dict[str, Any]:
        """Enhanced crawl method with markdown generation"""
        try:
            logging.info(f"Crawling URL: {url}")

            # Implement rate limiting
            current_time = time.time()
            time_since_last_request = current_time - self.last_request_time
            if time_since_last_request < self.rate_limit:
                await asyncio.sleep(self.rate_limit - time_since_last_request)

            # Configure crawler run settings
            run_config = CrawlerRunConfig(
                markdown_generator=self.markdown_generator,
                js_code=[
                    "window.scrollTo(0, document.body.scrollHeight);",
                    "await new Promise(r => setTimeout(r, 2000));"
                ],
                cache_mode=CacheMode.BYPASS
            )

            # Perform the crawl
            result = await crawler.arun(
                url=url,
                config=run_config
            )

            if result.success:
                # Generate filename from URL
                filename = url.split(
                    '/')[-2] if url.endswith('/') else url.split('/')[-1]
                filename = filename or 'index'

                # Save raw data
                raw_data = {
                    'url': url,
                    'lastmod': url_data.get('lastmod'),
                    'priority': url_data.get('priority'),
                    'html': result.raw_html if hasattr(result, 'raw_html') else '',
                    'crawl_time': datetime.now().isoformat()
                }

                raw_file = self.raw_dir / f"{filename}.json"
                async with aiofiles.open(raw_file, 'w') as f:
                    await f.write(json.dumps(raw_data, indent=2))

                # Save markdown
                if hasattr(result, 'markdown_v2'):
                    markdown_content = result.markdown_v2.fit_markdown
                else:
                    markdown_content = result.fit_markdown if hasattr(
                        result, 'fit_markdown') else result.markdown

                markdown_file = self.markdown_dir / f"{filename}.md"
                async with aiofiles.open(markdown_file, 'w') as f:
                    await f.write(markdown_content)

                # Return processed data
                page_data = {
                    'url': url,
                    'filename': filename,
                    'raw_path': str(raw_file),
                    'markdown_path': str(markdown_file),
                    'crawl_time': datetime.now().isoformat()
                }

                logging.info(f"Successfully crawled and saved: {url}")
                return page_data

            else:
                logging.warning(f"Failed to crawl: {url}")
                return None

        except Exception as e:
            logging.error(f"Error crawling {url}: {e}", exc_info=True)
            return None
        finally:
            self.last_request_time = time.time()

    async def process_batch(self, batch: List[Dict[str, Any]], crawler: AsyncWebCrawler) -> List[Dict[str, Any]]:
        """Process a batch of URLs in parallel."""
        tasks = []
        for url_data in batch:
            url = url_data['loc']
            tasks.append(self.crawl_single_url(url, url_data, crawler))
        return await asyncio.gather(*tasks)

    async def crawl_urls(self, urls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Crawl URLs in parallel batches."""
        results = []

        async with AsyncWebCrawler(
            config=self.browser_config,
            max_concurrent_requests=config.MAX_CONCURRENT_REQUESTS
        ) as crawler:
            for i in range(0, len(urls), config.BATCH_SIZE):
                batch = urls[i:i + config.BATCH_SIZE]
                batch_results = await self.process_batch(batch, crawler)
                results.extend([r for r in batch_results if r is not None])

        return results

    async def combine_markdown_files(self, results: List[Dict[str, Any]]) -> None:
        """Combine all markdown files into a single final.md"""
        try:
            combined_content = []

            # Sort results by filename to maintain consistent order
            sorted_results = sorted(
                results, key=lambda x: x.get('filename', ''))

            for result in sorted_results:
                if result and 'markdown_path' in result:
                    try:
                        async with aiofiles.open(result['markdown_path'], 'r') as f:
                            content = await f.read()
                            # Add a header with the original URL
                            header = f"\n\n## {result['url']}\n\n"
                            combined_content.append(header + content)
                    except Exception as e:
                        logging.error(f"Error reading markdown file {
                                      result['markdown_path']}: {e}")

            if combined_content:
                final_file = self.output_dir / 'final.md'
                async with aiofiles.open(final_file, 'w') as f:
                    await f.write('\n'.join(combined_content))
                logging.info(f"Successfully created final.md at {final_file}")
            else:
                logging.warning("No content to combine into final.md")

        except Exception as e:
            logging.error(f"Error combining markdown files: {
                          e}", exc_info=True)

    async def process_sitemap(self, url: str) -> List[Dict[str, Any]]:
        """Process sitemap and combine results"""
        # Get URLs and crawl them
        urls = await self.fetch_sitemap(url)
        if not urls:
            logging.error("No URLs found in sitemap")
            return []

        # Save sitemap to XML file
        urlset = ET.Element(
            'urlset', xmlns='http://www.sitemaps.org/schemas/sitemap/0.9')
        for url_data in urls:
            url_elem = ET.SubElement(urlset, 'url')
            loc = ET.SubElement(url_elem, 'loc')
            loc.text = url_data['loc']

        tree = ET.ElementTree(urlset)
        tree.write(str(self.output_dir / config.SITEMAP_OUTPUT),
                   encoding='utf-8', xml_declaration=True)
        logging.info(f"Sitemap saved to {config.SITEMAP_OUTPUT}")

        # Crawl URLs and get results
        results = await self.crawl_urls(urls)

        # Combine markdown files
        await self.combine_markdown_files(results)

        # Save summary
        summary = {
            'total_urls': len(urls),
            'successful_crawls': len(results),
            'crawl_time': datetime.now().isoformat(),
            'processed_urls': results
        }

        async with aiofiles.open(self.output_dir / config.SUMMARY_FILE, 'w') as f:
            await f.write(json.dumps(summary, indent=2))

        return results


async def main():
    scraper = SitemapScraper(output_dir=config.OUTPUT_DIR)
    logging.info(f"Starting scrape of website: {config.WEBSITE_URL}")

    start_time = time.time()
    results = await scraper.process_sitemap(config.WEBSITE_URL)
    end_time = time.time()

    duration = end_time - start_time
    logging.info(f"Scraping complete! Processed {
                 len(results)} URLs in {duration:.2f} seconds")
    logging.info(f"Results saved in: {config.OUTPUT_DIR}")

if __name__ == "__main__":
    asyncio.run(main())
