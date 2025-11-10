""" Convert a pdf file with a given filepath to a markdown file in a specified directory. """
import argparse
import logging
import os
from configparser import ConfigParser
from os import PathLike

from marker.config.parser import ConfigParser
from marker.converters.pdf import PdfConverter
from marker.models import create_model_dict
from marker.output import save_output

from src.configs.pdf_extractor_config import extractor_ollama_config

logger = logging.getLogger(__name__)


def convert_pdf_to_markdown(pdf_path: PathLike, output_path: PathLike = None) -> int:
    '''
    This function will create a new folder using the pdfs name where it stores the markdown, pictures and meta.json file.
    The output files will be named exactly like the pdf or keep their internal naming from marker for the pictures.
    :param pdf_path: path of the pdf file to process
    :param output_path: path where the output folder is created
    :return: None
    '''

    logging.info(
        f'starting conversion of pdf file: \n{pdf_path}\nto markdown \n{output_path}'
    )

    # checking arguments
    if not pdf_path or not os.path.exists(pdf_path):
        logger.error('no or faulty pdf file provided')
        return 0
    pdf_path = str(pdf_path)
    if not output_path:
        output_path = os.getcwd()
        logger.warning('no output path provided, using cwd')
    elif str(output_path).endswith('.md'):
        output_path, fname = os.path.split(output_path)
        fname = os.path.splitext(fname)[0]
    else:
        # infer the rest of the needed filepaths
        pdf_name = os.path.basename(pdf_path)
        fname = os.path.splitext(pdf_name)[0]
        output_path = os.path.join(output_path, fname)
        os.makedirs(output_path, exist_ok=False)
    output_path = str(output_path)
    fname = str(fname)


    # set up a config, this could be altered for more flexibility
    config_parser = ConfigParser(extractor_ollama_config)

    try:
        converter = PdfConverter(
            config=config_parser.generate_config_dict(),
            artifact_dict=create_model_dict(),
            processor_list=config_parser.get_processors(),
            renderer=config_parser.get_renderer(),
            llm_service=config_parser.get_llm_service()
        )
        rendered = converter(pdf_path)
        save_output(rendered,
                    output_path,
                    fname)
        return 1
    except Exception as e:
        logger.error(e)
        return 0

def main():
    """
    Main function to call parse_pdf from the command line.
    Usage: python script.py --pdf path/to/pdf [--output path/to/output]
    """
    # Create argument parser
    parser = argparse.ArgumentParser(description='Convert PDF to Markdown using Marker')

    # Add required argument for PDF file path
    parser.add_argument('--pdf', type=str, required=True,
                        help='Path to the PDF file to be converted')

    # Add optional argument for output directory
    parser.add_argument('--output', type=str, default=None,
                        help='Path to the output directory (defaults to current working directory)')

    # Parse arguments
    args = parser.parse_args()

    # Validate PDF path
    if not os.path.exists(args.pdf):
        print(f"Error: PDF file not found at '{args.pdf}'")
        return 1

    # Call the parse_pdf function
    try:
        convert_pdf_to_markdown(pdf_path=args.pdf, output_path=args.output)
        return 0
    except Exception as e:
        print(f"Error during PDF conversion: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
