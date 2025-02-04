import asyncio
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import time
from datetime import datetime

from openai import OpenAI, APIError
from pinecone import Pinecone, ServerlessSpec
from langchain_core.documents import Document

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class EmbeddingProcessor:
    def __init__(
        self,
        batch_size: int = 1000,
        max_retries: int = 3,
        initial_retry_delay: float = 1.0,
        openai_model: str = "text-embedding-3-small",
        pinecone_index: str = "website-content"
    ):
        """Initialize the EmbeddingProcessor.

        Args:
            batch_size: Number of chunks to process in each batch
            max_retries: Maximum number of retry attempts for failed API calls
            initial_retry_delay: Initial delay (in seconds) before retrying
            openai_model: OpenAI embedding model to use
            pinecone_index: Name of the Pinecone index to use
        """
        self.batch_size = batch_size
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay
        self.openai_model = openai_model
        self.pinecone_index = pinecone_index

        # Initialize clients
        self.openai_client = OpenAI()
        self.pinecone_client = Pinecone()

        # Track processed items
        self.processed_count = 0
        self.failed_items = []

    async def prepare_batch_file(self, chunks: List[Document], batch_id: str) -> str:
        """Prepare a JSONL file for batch processing."""
        batch_file = Path(f"batch_input_{batch_id}.jsonl")

        try:
            with open(batch_file, 'w') as f:
                for i, chunk in enumerate(chunks):
                    request = {
                        "custom_id": f"{batch_id}_chunk_{i}",
                        "method": "POST",
                        "url": "/v1/embeddings",
                        "body": {
                            "model": self.openai_model,
                            "input": chunk.page_content,
                            "encoding_format": "float"
                        }
                    }
                    f.write(json.dumps(request) + '\n')

            logger.info(f"Created batch file {
                        batch_file} with {len(chunks)} chunks")
            return str(batch_file)

        except Exception as e:
            logger.error(f"Error creating batch file: {str(e)}")
            raise

    async def process_chunks(self, chunks: List[Document], batch_id: str) -> List[Dict[str, Any]]:
        """Process a list of chunks through the OpenAI Batch API."""
        try:
            # Prepare batch file
            batch_file_path = await self.prepare_batch_file(chunks, batch_id)

            # Upload file for batch processing
            with open(batch_file_path, 'rb') as f:
                file = await self._with_retries(
                    lambda: self.openai_client.files.create(
                        file=f,
                        purpose="batch"
                    )
                )

            # Create batch job
            batch = await self._with_retries(
                lambda: self.openai_client.batches.create(
                    input_file_id=file.id,
                    endpoint="/v1/embeddings",
                    completion_window="24h"
                )
            )

            # Wait for batch completion
            while True:
                status = await self._with_retries(
                    lambda: self.openai_client.batches.retrieve(batch.id)
                )

                if status.status in ['completed', 'failed']:
                    break

                await asyncio.sleep(10)  # Check every 10 seconds
                logger.info(f"Batch {batch.id} status: {status.status}")

            if status.status == 'failed':
                raise Exception(f"Batch {batch.id} failed: {status.error}")

            # Get results
            output = await self._with_retries(
                lambda: self.openai_client.files.content(status.output_file_id)
            )

            # Process results
            processed_items = []
            for i, (chunk, line) in enumerate(zip(chunks, output.text.splitlines())):
                result = json.loads(line)
                if result.get('error'):
                    self.failed_items.append({
                        'chunk': chunk,
                        'error': result['error']
                    })
                    continue

                processed_items.append({
                    'id': f"{chunk.metadata['url']}_{chunk.metadata['chunk_sequence']}",
                    'values': result['response']['body']['data'][0]['embedding'],
                    'metadata': {
                        'url': chunk.metadata['url'],
                        'chunk_sequence': chunk.metadata['chunk_sequence'],
                        'total_chunks': chunk.metadata['total_chunks_for_url'],
                        'timestamp': datetime.now().isoformat(),
                        'token_count': chunk.metadata.get('token_count', 0),
                        'chunk_size': chunk.metadata.get('chunk_size', 0)
                    }
                })

            self.processed_count += len(processed_items)
            logger.info(f"Successfully processed {
                        len(processed_items)} chunks")

            # Cleanup batch file
            Path(batch_file_path).unlink()

            return processed_items

        except Exception as e:
            logger.error(f"Error in batch processing: {str(e)}")
            raise

    async def store_vectors(self, vectors: List[Dict[str, Any]]):
        """Store vectors in Pinecone."""
        try:
            # Create index if it doesn't exist
            existing_indexes = self.pinecone_client.list_indexes()
            if self.pinecone_index not in [idx['name'] for idx in existing_indexes]:
                self.pinecone_client.create_index(
                    name=self.pinecone_index,
                    dimension=1536,  # Full dimensionality for text-embedding-3-small
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region="us-east-1"
                    )
                )
                logger.info(f"Created new Pinecone index: {
                            self.pinecone_index}")

            # Get index reference
            index = self.pinecone_client.Index(self.pinecone_index)

            # Upsert vectors in batches
            for i in range(0, len(vectors), 100):  # Pinecone recommended batch size
                batch = vectors[i:i + 100]
                await self._with_retries(
                    lambda: index.upsert(vectors=batch)
                )

            logger.info(f"Successfully stored {
                        len(vectors)} vectors in Pinecone")

        except Exception as e:
            logger.error(f"Error storing vectors: {str(e)}")
            raise

    async def _with_retries(self, operation, current_retry: int = 0):
        """Execute an operation with exponential backoff retry logic."""
        try:
            return operation()
        except Exception as e:
            if current_retry >= self.max_retries:
                raise

            delay = self.initial_retry_delay * (2 ** current_retry)
            logger.warning(f"Operation failed, retrying in {delay}s: {str(e)}")
            await asyncio.sleep(delay)

            return await self._with_retries(operation, current_retry + 1)

    async def process_and_store(self, chunks: List[Document]):
        """Process chunks and store them in Pinecone."""
        timestamp = int(time.time())
        total_chunks = len(chunks)
        logger.info(f"Starting to process {total_chunks} chunks")

        # Process chunks in batches
        for i in range(0, total_chunks, self.batch_size):
            batch = chunks[i:i + self.batch_size]
            batch_id = f"batch_{timestamp}_{i//self.batch_size}"
            vectors = await self.process_chunks(batch, batch_id)
            await self.store_vectors(vectors)

            logger.info(f"Completed batch {
                        i//self.batch_size + 1} of {(total_chunks + self.batch_size - 1)//self.batch_size}")

        logger.info(f"""
        Processing complete:
        - Total processed: {self.processed_count}
        - Failed items: {len(self.failed_items)}
        """)

        if self.failed_items:
            logger.warning("Failed items details:", self.failed_items)
