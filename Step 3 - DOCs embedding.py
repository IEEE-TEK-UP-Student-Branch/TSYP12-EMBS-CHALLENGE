from langchain_community.vectorstores.utils import filter_complex_metadata
import json
from pathlib import Path
import chromadb
from chromadb.utils import embedding_functions
from tqdm.notebook import tqdm
import logging
from datetime import datetime
import time
from typing import List, Dict, Generator
from uuid import uuid4

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('embeddings_generator')
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma

CLEANED_PDFS_DIR = Path("cleaned_pdfs")
CHROMA_DB_DIR = Path("chroma_db")

# Ollama Configuration
OLLAMA_MODEL = "mistral-nemo:12b-instruct-2407-q2_K"
OLLAMA_URL = "http://localhost:11434"

# Batch Processing
BATCH_SIZE = 10
DELAY_BETWEEN_BATCHES = 0.1  # seconds

def load_document(json_path: Path) -> Dict:
    """Load a processed document from JSON."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load document {json_path}: {e}")
        return None
    
def paragraph_generator(json_files: List[Path]) -> Generator[Dict, None, None]:
    """Generate paragraphs from JSON files in batches."""
    for json_path in json_files:
        doc = load_document(json_path)
        if not doc:
            continue

        for paragraph in doc['paragraphs']:
            # Create a unique ID using source file and position

            para_id = f"{doc['filename']}_{paragraph['page_number']}_{paragraph['position']}"

            # Create metadata
            metadata = {
                'source_file': doc['filename'],
                'page_number': paragraph['page_number'],
                'position': paragraph['position'],
                'word_count': paragraph['word_count'],
                'total_pages': doc['total_pages'],
                'processed_date': doc['processed_date']
            }

            # Add document metadata if available
            if doc.get('metadata'):
                metadata['doc_metadata'] = json.dumps(doc['metadata'])

            d = Document(
                page_content=paragraph['text'],
                metadata=metadata,
                id=para_id,
            )

            yield d
            

def setup_chroma_client() -> chromadb.PersistentClient:
    """Initialize the Chroma client with persistence."""
    try:
        # Ensure the directory exists
        CHROMA_DB_DIR.mkdir(parents=True, exist_ok=True)

        # Create embedding function
        embeddings = OllamaEmbeddings(
            model="mistral-nemo:12b-instruct-2407-q2_K")

        # Create persistent client
        vector_store = Chroma(
            collection_name="pdf_paragraphs",
            embedding_function=embeddings,
            # Where to save data locally, remove if not necessary
            persist_directory=str(CHROMA_DB_DIR),
        )

        return vector_store

    except Exception as e:
        logger.error(f"Failed to setup Chroma client: {e}")
        raise
    

def process_paragraphs(vector_store, paragraphs: List[Dict]) -> None:
    """Process a batch of paragraphs and add to vector_store."""
    try:
        uuids = [str(uuid4()) for _ in range(len(paragraphs))]

        vector_store.add_documents(documents=paragraphs, ids=uuids)

    except Exception as e:
        logger.error(f"Failed to process batch: {e}")
        # Log the problematic batch for debugging
        logger.debug(f"Problematic batch: {paragraphs}")
        
        
def embed_all_paragraphs() -> None:
    """Main function to embed all paragraphs."""
    try:
        # Check if input directory exists
        if not CLEANED_PDFS_DIR.exists():
            raise FileNotFoundError(f"Directory not found: {CLEANED_PDFS_DIR}")

        # Get all JSON files
        json_files = list(CLEANED_PDFS_DIR.glob("*.json"))
        if not json_files:
            logger.warning(f"No JSON files found in {CLEANED_PDFS_DIR}")
            return

        logger.info(f"Found {len(json_files)} JSON files to process")

        # Setup Chroma
        collection = setup_chroma_client()

        # Process paragraphs in batches
        current_batch = []
        total_processed = 0

        # Process paragraphs
        for paragraph in tqdm(paragraph_generator(json_files), desc="Processing paragraphs", unit="para"):
            current_batch.append(paragraph)

            if len(current_batch) >= BATCH_SIZE:
                process_paragraphs(collection, current_batch)
                total_processed += len(current_batch)
                current_batch = []
                time.sleep(DELAY_BETWEEN_BATCHES)

        # Process remaining paragraphs
        if current_batch:
            process_paragraphs(collection, current_batch)
            total_processed += len(current_batch)

        # Log completion
        logger.info(f"Successfully embedded {total_processed} paragraphs")
        logger.info(f"Vector database saved to: {CHROMA_DB_DIR}")

    except Exception as e:
        logger.error(f"Embedding process failed: {e}")
        raise
    

def main():
    embed_all_paragraphs()