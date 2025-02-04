import logging
import asyncio
from pathlib import Path
import os
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
from dotenv import load_dotenv

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_openai_standard_connection():
    """Test OpenAI API connection and basic embedding generation"""
    try:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

        # Test embedding generation
        test_text = "Testing OpenAI connection"
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=test_text,
            encoding_format="float"
        )

        logger.info("OpenAI Standard API Connection: ✅")
        logger.info(f"Generated embedding dimension: {
                    len(response.data[0].embedding)}")
        return True
    except Exception as e:
        logger.error(
            f"OpenAI Standard API Connection Failed: ❌\nError: {str(e)}")
        return False


async def test_openai_batch_connection():
    """Test OpenAI Batch API functionality"""
    try:
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

        # Create test batch file
        test_file = Path("test_batch.jsonl")
        test_file.write_text(
            '{"custom_id": "test_1", "method": "POST", "url": "/v1/embeddings", '
            '"body": {"model": "text-embedding-3-small", "input": "test content", "encoding_format": "float"}}\n'
        )

        # Test file upload
        with open(test_file, 'rb') as f:
            file = client.files.create(
                file=f,
                purpose="batch"
            )

        # Test batch creation
        batch = client.batches.create(
            input_file_id=file.id,
            endpoint="/v1/embeddings",
            completion_window="24h"
        )

        # Clean up test file
        test_file.unlink()

        logger.info("OpenAI Batch API Connection: ✅")
        logger.info(f"Created test batch: {batch.id}")
        return True
    except Exception as e:
        logger.error(f"OpenAI Batch API Connection Failed: ❌\nError: {str(e)}")
        return False


async def test_pinecone_connection():
    """Test Pinecone connection and serverless configuration"""
    try:
        pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))

        # Test index creation with serverless spec
        test_index_name = "test-index"

        # List existing indexes
        existing_indexes = pc.list_indexes()
        logger.info(f"Existing indexes: {existing_indexes}")

        # Create index if it doesn't exist
        if test_index_name not in [idx['name'] for idx in existing_indexes]:
            pc.create_index(
                name=test_index_name,
                dimension=1536,  # text-embedding-3-small dimension
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region="us-east-1"
                )
            )
            logger.info(f"Created new test index: {test_index_name}")

        # Test basic operations
        index = pc.Index(test_index_name)

        # Test vector upsert
        test_vector = {
            'id': 'test-1',
            'values': [0.1] * 1536,
            'metadata': {'test': True}
        }

        index.upsert(vectors=[test_vector])

        logger.info("Pinecone Connection and Operations: ✅")
        return True
    except Exception as e:
        logger.error(f"Pinecone Connection Failed: ❌\nError: {str(e)}")
        return False


async def main():
    """Run all connection tests"""
    try:
        # Test all connections
        standard_api = await test_openai_standard_connection()
        batch_api = await test_openai_batch_connection()
        pinecone = await test_pinecone_connection()

        if standard_api and batch_api and pinecone:
            logger.info("All connections successful! ✅")
            logger.info("""
            Ready to process content with:
            - OpenAI text-embedding-3-small
            - OpenAI Batch API
            - Pinecone Serverless
            """)
        else:
            logger.error("Some connections failed! ❌")

    except Exception as e:
        logger.error(f"Error in connection testing: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
