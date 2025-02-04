from typing import List, Dict, Optional
from pathlib import Path
import asyncio
import logging
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import tiktoken

from text_processor.embeddings import EmbeddingProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ContentChunker:
    def __init__(
        self,
        chunk_size: int = 3000,
        chunk_overlap: int = 100,
        embedding_processor: Optional[EmbeddingProcessor] = None
    ):
        """Initialize the ContentChunker with specific parameters."""
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.embedding_processor = embedding_processor or EmbeddingProcessor()

        # Initialize the markdown-aware text splitter
        self.text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name="cl100k_base",  # text-embedding-3-small encoder
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[
                "\n## ",      # Main headers
                "\n\n",       # Paragraphs
                "\n",         # Lines
                ".",          # Sentences
                " ",         # Words
                ""          # Characters
            ]
        )

    async def process_file(self, file_path: str, process_embeddings: bool = True) -> List[Document]:
        """Process a markdown file and return chunks."""
        try:
            content = await self._read_file(file_path)
            chunks = await self.process_content(content)

            logger.info(f"Successfully processed {
                        len(chunks)} chunks from {file_path}")

            if process_embeddings and chunks:
                await self.embedding_processor.process_and_store(chunks)

            return chunks

        except Exception as e:
            logger.error(f"Error processing file {file_path}: {str(e)}")
            raise

    async def _read_file(self, file_path: str) -> str:
        """Read file content asynchronously."""
        try:
            path = Path(file_path)
            return await asyncio.to_thread(path.read_text, encoding='utf-8')
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {str(e)}")
            raise

    async def process_content(self, content: str) -> List[Document]:
        """Process content and create chunks maintaining URL context."""
        try:
            chunks = []
            current_url = None
            current_content = []
            url_chunk_counter = {}  # Keep track of chunks per URL

            for line in content.split('\n'):
                # New URL section starts
                if line.startswith('## http'):
                    # Process previous URL content if exists
                    if current_content and current_url:
                        sub_chunks = await self._create_sub_chunks(
                            '\n'.join(current_content),
                            current_url,
                            url_chunk_counter.get(current_url, 0)
                        )
                        chunks.extend(sub_chunks)
                        url_chunk_counter[current_url] = len(sub_chunks)

                    # Reset for new URL
                    current_url = line.replace('## ', '').strip()
                    current_content = []
                    if current_url not in url_chunk_counter:
                        url_chunk_counter[current_url] = 0
                else:
                    current_content.append(line)

            # Process the last section
            if current_content and current_url:
                final_chunks = await self._create_sub_chunks(
                    '\n'.join(current_content),
                    current_url,
                    url_chunk_counter.get(current_url, 0)
                )
                chunks.extend(final_chunks)

            return chunks

        except Exception as e:
            logger.error(f"Error processing content: {str(e)}")
            raise

    async def _create_sub_chunks(self, content: str, url: str, start_index: int) -> List[Document]:
        """Create sub-chunks for content from the same URL."""
        try:
            sub_chunks = []
            raw_chunks = self.text_splitter.split_text(content)

            for i, chunk in enumerate(raw_chunks):
                # Skip empty chunks
                if not chunk.strip():
                    continue

                token_count = len(self._count_tokens(chunk))

                # Create document with metadata
                doc = Document(
                    page_content=chunk,
                    metadata={
                        "url": url,
                        "chunk_sequence": i + start_index,
                        "total_chunks_for_url": len(raw_chunks),
                        "token_count": token_count,
                        "chunk_size": len(chunk)
                    }
                )
                sub_chunks.append(doc)

                # Log warning if chunk is close to token limit
                if token_count > 7000:  # Warning threshold
                    logger.warning(f"Large chunk detected for {
                                   url}: {token_count} tokens")

            return sub_chunks

        except Exception as e:
            logger.error(f"Error creating sub-chunks: {str(e)}")
            raise

    def _count_tokens(self, text: str) -> List[int]:
        """Count tokens using tiktoken."""
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            return encoding.encode(text)
        except Exception as e:
            logger.error(f"Error counting tokens: {str(e)}")
            raise


async def main():
    """Main function for direct script execution."""
    try:
        # Initialize processors
        embedding_processor = EmbeddingProcessor(
            batch_size=1000,  # Process 1000 chunks at a time
            pinecone_index="website-content"  # Index name in Pinecone
        )

        chunker = ContentChunker(
            chunk_size=3000,
            chunk_overlap=100,
            embedding_processor=embedding_processor
        )

        # Get the path to final.md relative to the script location
        current_dir = Path(__file__).parent.parent
        final_md_path = current_dir / "scraped_data" / "final.md"

        logger.info(f"Processing file: {final_md_path}")

        # Process the file and generate embeddings
        chunks = await chunker.process_file(str(final_md_path), process_embeddings=True)

        # Display results
        logger.info("\n=== Processing Results ===")
        logger.info(f"Total chunks created: {len(chunks)}")

        # Group chunks by URL for display
        url_chunks = {}
        for chunk in chunks:
            url = chunk.metadata["url"]
            if url not in url_chunks:
                url_chunks[url] = []
            url_chunks[url].append(chunk)

        # Show sample chunks with metadata, grouped by URL
        logger.info("\n=== Sample Chunks by URL ===")
        # Show first 2 URLs
        for url, url_chunk_list in list(url_chunks.items())[:2]:
            logger.info(f"\nURL: {url}")
            logger.info(f"Total chunks for URL: {len(url_chunk_list)}")

            # Show first chunk for this URL
            sample_chunk = url_chunk_list[0]
            logger.info("=" * 50)
            logger.info(f"First Chunk Preview: {
                        sample_chunk.page_content[:200]}...")
            logger.info(f"Metadata: {sample_chunk.metadata}")
            logger.info("=" * 50)

        logger.info("\nProcessing and embedding completed successfully!")

    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
