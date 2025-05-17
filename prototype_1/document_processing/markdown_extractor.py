"""Extract markdown from PDFs in a directory structure"""
import os
import argparse
import subprocess
from pathlib import Path


class MarkdownExtractor:
    """
    Extracts markdown from PDF files using the marker_single utility.
    
    This class manages the batch extraction of multiple PDFs into markdown,
    handling directory traversal and processing decisions.
    """
    
    def __init__(self, language='English', batch_multiplier=2, max_pages=100):
        """
        Initialize the markdown extractor with extraction parameters.
        
        Args:
            language: Language of the PDF content
            batch_multiplier: Controls processing batch size
            max_pages: Maximum pages to process per document
        """
        self.language = language
        self.batch_multiplier = batch_multiplier
        self.max_pages = max_pages
        
    def extract_from_pdf(self, pdf_path, language=None, batch_multiplier=None, max_pages=None):
        """
        Extract markdown from a single PDF file.
        
        Args:
            pdf_path: Path to the PDF file or its containing directory
            language: Override default language
            batch_multiplier: Override default batch multiplier
            max_pages: Override default max pages
            
        Returns:
            bool: True if extraction was successful
        """
        # Use instance defaults if not specified
        language = language if language else self.language
        batch_multiplier = batch_multiplier if batch_multiplier else self.batch_multiplier
        max_pages = max_pages if max_pages else self.max_pages
        
        # Determine paths
        if str(pdf_path).endswith('.pdf'):
            dir_path = os.path.split(pdf_path)[0]
        else:
            dir_path = pdf_path
            # Find PDF in directory
            for file in os.listdir(dir_path):
                if file.endswith('.pdf'):
                    pdf_path = os.path.join(dir_path, file)
                    break
            else:
                print(f"No PDF file found in {dir_path}")
                return False
        
        # Build command
        cmd = [
            "marker_single",
            pdf_path,
            dir_path,
            "--batch_multiplier", str(batch_multiplier),
            "--max_pages", str(max_pages),
            "--langs", language
        ]
        
        # Execute command
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return True
        except subprocess.CalledProcessError as e:
            print(f"Error extracting markdown: {e}")
            print(f"Command output: {e.stdout}")
            print(f"Error output: {e.stderr}")
            return False
            
    def has_markdown(self, path):
        """
        Check if markdown files exist in a directory.
        
        Args:
            path: Directory to check
            
        Returns:
            bool: True if markdown files exist
        """
        path = Path(path)
        if not path.exists() or not path.is_dir():
            return False
            
        return any(f.suffix == '.md' for f in path.glob('*'))
        
    def process_library(self, library_path, overwrite=False):
        """
        Process all PDFs in a library directory structure.
        
        Args:
            library_path: Path to library directory
            overwrite: Whether to reprocess existing files
            
        Returns:
            int: Number of files successfully processed
        """
        library_path = Path(library_path)
        if not library_path.exists():
            raise ValueError(f"Library path does not exist: {library_path}")
            
        processed_count = 0
        
        # Walk through directory structure
        for item in library_path.glob('**'):
            if item.is_dir():
                print(f"Processing directory: {item}")
                if not self.has_markdown(item) or overwrite:
                    if self.extract_from_pdf(item):
                        processed_count += 1
                        
        print(f"Finished processing {processed_count} documents")
        return processed_count


def main():
    """Command-line interface for batch extraction"""
    parser = argparse.ArgumentParser(description="Extract markdown from PDFs in a Zotero library")
    parser.add_argument("-p", "--path", required=True, help="Path to the Zotero storage")
    parser.add_argument("-l", "--language", default="English", help="Document language")
    parser.add_argument("-o", "--overwrite", action="store_true", help="Overwrite existing files")
    
    args = parser.parse_args()
    
    print(f"Starting extraction from {args.path}")
    extractor = MarkdownExtractor(language=args.language)
    extractor.process_library(args.path, overwrite=args.overwrite)


if __name__ == '__main__':
    main()
