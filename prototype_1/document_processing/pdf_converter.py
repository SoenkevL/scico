"""PDF to Markdown conversion utilities"""
from marker.converters.pdf import PdfConverter as MarkerPdfConverter
from marker.models import create_model_dict
from marker.config.parser import ConfigParser
from marker.output import save_output
import os
import argparse


class PdfConverter:
    """
    Converts PDF documents to markdown format using the Marker library.
    
    This class provides a clean interface for PDF conversion operations,
    with configurable LLM settings for optimal extraction.
    """
    
    def __init__(self, llm_model="qwen3:14b", ollama_base_url="http://localhost:11434"):
        """
        Initialize the PDF converter with LLM settings.
        
        Args:
            llm_model: The name of the Ollama model to use
            ollama_base_url: The base URL for the Ollama service
        """
        self.config = {
            "output_format": "markdown",
            'use_llm': True,
            'llm_service': 'marker.services.ollama.OllamaService',
            'ollama_base_url': ollama_base_url,
            'ollama_model': llm_model
        }
        
    def convert(self, pdf_path, output_path=None):
        """
        Convert a PDF file to markdown.
        
        Args:
            pdf_path: Path to the PDF file
            output_path: Directory to save output (defaults to current directory)
            
        Returns:
            bool: True if conversion was successful, False otherwise
        """
        # Validate inputs
        if not pdf_path or not os.path.exists(pdf_path):
            raise ValueError('No or faulty PDF file provided')
            
        if not output_path:
            output_path = os.getcwd()
        
        # Set up output paths
        pdf_name = os.path.basename(pdf_path)
        fname = os.path.splitext(pdf_name)[0]
        full_output_path = os.path.join(output_path, fname)
        
        # Create config and converter
        config_parser = ConfigParser(self.config)
        converter = MarkerPdfConverter(
            config=config_parser.generate_config_dict(),
            artifact_dict=create_model_dict(),
            processor_list=config_parser.get_processors(),
            renderer=config_parser.get_renderer(),
            llm_service=config_parser.get_llm_service()
        )
        
        # Perform conversion
        try:
            rendered = converter(pdf_path)
            save_output(rendered, full_output_path, fname)
            return True
        except Exception as e:
            print(f"Error during PDF conversion: {e}")
            return False


def main():
    """Command-line interface for PDF conversion"""
    parser = argparse.ArgumentParser(description='Convert PDF to Markdown using Marker')
    parser.add_argument('--pdf', type=str, required=True,
                        help='Path to the PDF file to be converted')
    parser.add_argument('--output', type=str, default=None,
                        help='Path to the output directory')
    parser.add_argument('--model', type=str, default="qwen3:14b",
                        help='LLM model to use for conversion')
    
    args = parser.parse_args()
    
    # Validate output path if provided
    if args.output and not os.path.exists(args.output):
        print(f"Creating output directory: {args.output}")
        try:
            os.makedirs(args.output)
        except Exception as e:
            print(f"Error creating output directory: {e}")
            return 1
    
    # Perform conversion
    converter = PdfConverter(llm_model=args.model)
    success = converter.convert(args.pdf, args.output)
    
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
