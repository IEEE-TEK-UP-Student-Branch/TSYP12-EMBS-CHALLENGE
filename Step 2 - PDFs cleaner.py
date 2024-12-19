import os
from pathlib import Path
import PyPDF2
import re
import unicodedata
from typing import List, Dict, Optional
import json
from tqdm.notebook import tqdm
import logging
from dataclasses import dataclass
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('pdf_cleaner')

@dataclass
class Paragraph:
    """Represents a cleaned paragraph from a PDF."""
    text: str
    page_number: int
    position: int  # Position within the page
    word_count: int
    source_file: str
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'text': self.text,
            'page_number': self.page_number,
            'position': self.position,
            'word_count': self.word_count,
            'source_file': self.source_file
        }

@dataclass
class PDFDocument:
    """Represents a processed PDF document."""
    filename: str
    path: Path
    paragraphs: List[Paragraph]
    total_pages: int
    processed_date: str
    metadata: Dict
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            'filename': self.filename,
            'path': str(self.path),
            'paragraphs': [p.to_dict() for p in self.paragraphs],
            'total_pages': self.total_pages,
            'processed_date': self.processed_date,
            'metadata': self.metadata
        }
        
        
def normalize_text(text: str) -> str:
    """
    Normalize text by handling unicode characters and removing unwanted elements.
    """
    # Normalize unicode characters
    text = unicodedata.normalize('NFKD', text)
    
    # Remove non-printable characters except newlines and tabs
    text = ''.join(char for char in text if char.isprintable() or char in '\n\t')
    
    # Replace various types of dashes and hyphens with standard hyphen
    text = re.sub(r'[‐‑‒–—―]', '-', text)
    
    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    return text.strip()

def clean_paragraph(text: str) -> str:
    """
    Clean a paragraph of text by removing common PDF artifacts and formatting issues.
    """
    # Remove header/footer patterns (e.g., page numbers, dates)
    text = re.sub(r'^\d+$', '', text)  # Standalone numbers (likely page numbers)
    text = re.sub(r'^\d{1,2}/\d{1,2}/\d{2,4}$', '', text)  # Dates
    
    # Remove common PDF artifacts
    text = re.sub(r'^\s*\[?Page \d+\]?\s*$', '', text)  # Page markers
    text = re.sub(r'^\s*-\d+-\s*$', '', text)  # Page numbers with dashes
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove lines that are just decorative (e.g., "----", "____")
    text = re.sub(r'^\s*[-_=]{3,}\s*$', '', text)
    
    return text.strip()

def is_valid_paragraph(text: str, min_words: int = 5, max_words: int = 1000) -> bool:
    """
    Check if a paragraph is valid based on various criteria.
    """
    # Skip if empty after cleaning
    if not text.strip():
        return False
    
    # Count words
    word_count = len(text.split())
    if word_count < min_words or word_count > max_words:
        return False
    
    # Skip if it's likely a header/footer
    if re.match(r'^\d+$', text):  # Just numbers
        return False
    if re.match(r'^\d{1,2}/\d{1,2}/\d{2,4}$', text):  # Just a date
        return False
    if re.match(r'^\s*[Pp]age \d+\s*$', text):  # Just "Page X"
        return False
    
    return True


def extract_pdf_metadata(reader: PyPDF2.PdfReader) -> Dict:
    """Extract and clean PDF metadata."""
    try:
        metadata = reader.metadata
        if metadata:
            # Convert to dict and clean up
            return {
                k.lower(): str(v) for k, v in metadata.items()
                if v is not None and str(v).strip()
            }
    except Exception as e:
        logger.warning(f"Could not extract metadata: {e}")
    
    return {}

def extract_paragraphs_from_page(
    text: str,
    page_number: int,
    source_file: str,
    min_words: int = 5
) -> List[Paragraph]:
    """
    Extract valid paragraphs from a page of text.
    """
    # Split text into potential paragraphs
    raw_paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
    
    paragraphs = []
    for pos, raw_text in enumerate(raw_paragraphs):
        # Clean and normalize the text
        cleaned_text = clean_paragraph(normalize_text(raw_text))
        
        # Skip if not valid
        if not is_valid_paragraph(cleaned_text, min_words=min_words):
            continue
        
        # Create paragraph object
        word_count = len(cleaned_text.split())
        paragraph = Paragraph(
            text=cleaned_text,
            page_number=page_number,
            position=pos,
            word_count=word_count,
            source_file=source_file
        )
        
        paragraphs.append(paragraph)
    
    return paragraphs

def process_pdf(pdf_path: Path) -> Optional[PDFDocument]:
    """
    Process a PDF file and extract clean paragraphs.
    """
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            
            # Extract metadata
            metadata = extract_pdf_metadata(reader)
            
            all_paragraphs = []
            total_pages = len(reader.pages)
            
            # Process each page
            for page_num, page in enumerate(reader.pages):
                try:
                    text = page.extract_text()
                    if not text:
                        continue
                    
                    paragraphs = extract_paragraphs_from_page(
                        text,
                        page_number=page_num + 1,
                        source_file=str(pdf_path)
                    )
                    all_paragraphs.extend(paragraphs)
                    
                except Exception as e:
                    logger.warning(f"Error processing page {page_num + 1} in {pdf_path}: {e}")
                    continue
            
            # Create document object
            document = PDFDocument(
                filename=pdf_path.name,
                path=pdf_path,
                paragraphs=all_paragraphs,
                total_pages=total_pages,
                processed_date=datetime.now().isoformat(),
                metadata=metadata
            )
            
            return document
            
    except Exception as e:
        logger.error(f"Failed to process PDF {pdf_path}: {e}")
        return None
    
    
def save_document(doc: PDFDocument, output_dir: Path) -> None:
    """Save processed document to JSON file."""
    try:
        # Create output directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create output filename
        output_file = output_dir / f"{doc.filename}.json"
        
        # Save to JSON
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(doc.to_dict(), f, ensure_ascii=False, indent=2)
            
    except Exception as e:
        logger.error(f"Failed to save document {doc.filename}: {e}")

def process_directory(
    input_dir: Path,
    output_dir: Path,
    recursive: bool = True
) -> None:
    """
    Process all PDFs in a directory and its subdirectories.
    """
    # Find all PDF files
    pattern = "**/*.pdf" if recursive else "*.pdf"
    pdf_files = list(input_dir.glob(pattern))
    
    if not pdf_files:
        logger.warning(f"No PDF files found in {input_dir}")
        return
    
    logger.info(f"Found {len(pdf_files)} PDF files to process")
    
    # Process each PDF
    for pdf_path in tqdm(pdf_files, desc="Processing PDFs"):
        try:
            # Process the PDF
            document = process_pdf(pdf_path)
            if document and document.paragraphs:
                # Save the processed document
                save_document(document, output_dir)
                logger.info(f"Successfully processed {pdf_path.name}: "
                          f"{len(document.paragraphs)} paragraphs extracted")
            else:
                logger.warning(f"No valid paragraphs found in {pdf_path.name}")
                
        except Exception as e:
            logger.error(f"Error processing {pdf_path.name}: {e}")
            continue
        
        
if __name__ == "__main__":
    # Set up directories
    input_dir = Path("downloads")
    output_dir = Path("cleaned_pdfs")
    
    # Process PDFs
    process_directory(input_dir, output_dir, recursive=True)