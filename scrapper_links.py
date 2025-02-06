import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

import aiofiles
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator
from crawl4ai.content_filter_strategy import PruningContentFilter


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s]: %(message)s"
)


class LinksScraper:
    def __init__(self, links_file: str = "links.txt", output_dir: str = "scraped_data"):
        self.links_file = Path(links_file)
        self.output_dir = Path(output_dir)
        self.raw_dir = self.output_dir / 'raw_links'
        self.markdown_dir = self.output_dir / 'markdown_links'

        # Ensure output directories exist
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.markdown_dir.mkdir(parents=True, exist_ok=True)

        self.rate_limit = 1  # seconds between requests
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
                threshold=0.48,
                threshold_type="fixed",
                min_word_threshold=10
            ),
            options={
                "ignore_links": False,
                "escape_html": True,
                "body_width": 80
            }
        )

    async def read_links(self) -> List[str]:
        links = []
        async with aiofiles.open(self.links_file, "r") as f:
            async for line in f:
                line = line.strip()
                if line:
                    links.append(line)
        logging.info(f"Read {len(links)} links from {self.links_file}")
        return links

    async def crawl_single_url(self, url: str, crawler: AsyncWebCrawler) -> Dict[str, Any]:
        try:
            logging.info(f"Crawling URL: {url}")
            current_time = time.time()
            elapsed = current_time - self.last_request_time
            if elapsed < self.rate_limit:
                await asyncio.sleep(self.rate_limit - elapsed)

            run_config = CrawlerRunConfig(
                markdown_generator=self.markdown_generator,
                js_code=[
                    "window.scrollTo(0, document.body.scrollHeight);",
                    "await new Promise(r => setTimeout(r, 2000));"
                ],
                cache_mode=CacheMode.BYPASS
            )

            result = await crawler.arun(url=url, config=run_config)
            if result.success:
                filename = url.split("/")[-2] if url.endswith("/") else url.split("/")[-1]
                filename = filename if filename else "index"

                raw_data = {
                    "url": url,
                    "html": result.raw_html if hasattr(result, "raw_html") else "",
                    "crawl_time": datetime.now().isoformat()
                }
                raw_file = self.raw_dir / f"{filename}.json"
                async with aiofiles.open(raw_file, "w") as f:
                    await f.write(json.dumps(raw_data, indent=2))

                if hasattr(result, "markdown_v2"):
                    markdown_content = result.markdown_v2.fit_markdown
                elif hasattr(result, "fit_markdown"):
                    markdown_content = result.fit_markdown
                else:
                    markdown_content = result.markdown if hasattr(result, "markdown") else ""

                markdown_file = self.markdown_dir / f"{filename}.md"
                async with aiofiles.open(markdown_file, "w") as f:
                    await f.write(markdown_content)

                logging.info(f"Successfully crawled: {url}")
                return {
                    "url": url,
                    "filename": filename,
                    "raw_path": str(raw_file),
                    "markdown_path": str(markdown_file),
                    "crawl_time": datetime.now().isoformat()
                }
            else:
                logging.warning(f"Failed to crawl: {url}")
                return {}
        except Exception as e:
            logging.error(f"Error crawling {url}: {e}")
            return {}
        finally:
            self.last_request_time = time.time()

    async def process_links(self) -> List[Dict[str, Any]]:
        links = await self.read_links()
        async with AsyncWebCrawler(
            config=self.browser_config,
            max_concurrent_requests=5
        ) as crawler:
            tasks = [self.crawl_single_url(url, crawler) for url in links]
            results = await asyncio.gather(*tasks)
        return [res for res in results if res]

    async def combine_markdown_files(self, results: List[Dict[str, Any]]) -> None:
        """Combine all markdown files into final.md"""
        try:
            final_path = self.output_dir / "final.md"
            combined = []

            for result in sorted(results, key=lambda x: x['filename']):
                if result.get('markdown_path'):
                    async with aiofiles.open(result['markdown_path'], 'r') as f:
                        content = await f.read()
                        combined.append(f"\n\n## {result['url']}\n\n{content}")

            async with aiofiles.open(final_path, 'w') as f:
                await f.write('\n'.join(combined))
            logging.info(f"Combined markdown saved to {final_path}")
        except Exception as e:
            logging.error(f"Error combining markdown: {e}")

    async def run(self):
        results = await self.process_links()
        await self.combine_markdown_files(results)
        logging.info(f"Crawled {len(results)} pages successfully.")


async def main():
    scraper = LinksScraper()
    await scraper.run()


    async def combine_markdown_files(self, results: List[Dict[str, Any]]) -> None:
        """Combine all markdown files into a single final.md"""
        try:
            combined_content = []
            for result in sorted(results, key=lambda x: x.get('filename', '')):
                if result and 'markdown_path' in result:
                    try:
                        async with aiofiles.open(result['markdown_path'], 'r') as f:
                            content = await f.read()
                            header = f"\n\n## {result['url']}\n\n"
                            combined_content.append(header + content)
                    except Exception as e:
                        logging.error(f"Error reading markdown file {result['markdown_path']}: {e}")

            # Write combined content to final.md
            final_path = self.output_dir / 'final.md'
            async with aiofiles.open(final_path, 'w') as f:
                await f.write('\n'.join(combined_content))

        except Exception as e:
            logging.error(f"Error combining markdown files: {e}")

    async def run(self) -> None:
        """Main execution method"""
        try:
            # Read links
            urls = await self.read_links()
            if not urls:
                logging.error("No URLs found in links file")
                return

            # Initialize crawler
            async with AsyncWebCrawler(
                config=self.browser_config,
                max_concurrent_requests=5
            ) as crawler:
                # Process URLs
                results = []
                for url in urls:
                    result = await self.crawl_single_url(url, crawler)
                    if result:
                        results.append(result)

                # Combine results
                await self.combine_markdown_files(results)

        except Exception as e:
            logging.error(f"Error in run method: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(main())
