import streamlit as st
import asyncio
from pathlib import Path
from scraper import SitemapScraper
from scrapper_links import LinksScraper
from llm_processor.llm_processor import BusinessModelAnalyzer
import os

st.set_page_config(
    page_title="Scraping Suite",
    page_icon="🕷️",
    layout="wide"
)


def main():
    st.title("🚀 LAF Web Scraping Dashboard")

    with st.sidebar:
        st.header("⚙️ Configuration")
        output_dir = st.text_input("Output Directory", "scraped_data")

    tab1, tab2, tab3 = st.tabs(
        ["🌐 Sitemap Scraper", "🔗 URL List Scraper", "🧠 LLM Processing"])

    with tab1:
        sitemap_scraper_ui(output_dir)

    with tab2:
        link_scraper_ui(output_dir)

    with tab3:
        llm_processing_ui()


def sitemap_scraper_ui(output_dir):
    st.subheader("Sitemap Scraper")
    url = st.text_input("Enter Website URL", "https://example.com")

    if st.button("Scrape Sitemap"):
        try:
            with st.spinner("Discovering and scraping sitemap..."):
                scraper = SitemapScraper(output_dir=output_dir)
                asyncio.run(scraper.scrape_sitemap(url))
            st.success("Successfully scraped sitemap")
            display_results(scraper.raw_dir, scraper.markdown_dir)
        except Exception as e:
            st.error(f"Sitemap Error: {str(e)}")


def link_scraper_ui(output_dir):
    st.subheader("URL List Scraper")
    file_path = st.text_input("Path to links.txt", "links.txt")

    if st.button("Process Links"):
        try:
            with st.spinner("Processing links..."):
                scraper = LinksScraper(output_dir=output_dir)
                asyncio.run(scraper.process_links(file_path))
            st.success("Successfully processed links")
            display_results(scraper.raw_dir, scraper.markdown_dir)
        except FileNotFoundError:
            st.error("Could not find links file")
        except Exception as e:
            st.error(f"Processing Error: {str(e)}")


def llm_processing_ui():
    st.subheader("LLM Content Processing")
    api_key = st.text_input("OpenAI API Key", type="password")

    if api_key:
        os.environ['OPENAI_API_KEY'] = api_key
        processor = BusinessModelAnalyzer()
        if st.button("Process Latest Content"):
            try:
                with st.spinner("Analyzing content..."):
                    content = asyncio.run(processor.read_content())
                    if content:
                        result = asyncio.run(processor.analyze_business_model(content))
                        st.write(result)
                    else:
                        st.error("No content found to analyze")
            except Exception as e:
                st.error(f"LLM Error: {str(e)}")


def display_results(raw_dir, markdown_dir):
    st.subheader("Output Files")

    col1, col2 = st.columns(2)
    raw_path = Path(raw_dir)
    md_path = Path(markdown_dir)

    with col1:
        st.write("### Raw JSON Files")
        if not raw_path.exists():
            st.warning("No raw files found")
            return

        for json_file in raw_path.glob("*.json"):
            with open(json_file, "r") as f:
                st.download_button(
                    label=f"Download {json_file.name}",
                    data=f.read(),
                    file_name=json_file.name,
                    key=f"raw_{json_file.name}"
                )

    with col2:
        st.write("### Processed Markdown")
        if not md_path.exists():
            st.warning("No markdown files found")
            return

        for md_file in md_path.glob("*.md"):
            with open(md_file, "r") as f:
                st.download_button(
                    label=f"Download {md_file.name}",
                    data=f.read(),
                    file_name=md_file.name,
                    key=f"md_{md_file.name}"
                )


if __name__ == "__main__":
    main()
