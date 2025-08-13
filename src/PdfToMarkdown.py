# this file is used to convert a pdf to a markdown file

from marker.converters.pdf import PdfConverter
import argparse
from marker.models import create_model_dict
from marker.config.parser import ConfigParser
from marker.output import text_from_rendered, save_output
import os
from configs import extractor_ollama_config

def parse_pdf(pdf_path: [os.PathLike] = None, output_path :[os.PathLike] = None) -> None:
    '''
    THis function will create a new folder using the pdfs name where it stores the markdown, pictures and meta.json file.
    The output files will be named exactly like the pdf or keep their internal naming from marker for the pictures.
    :param pdf_path: path of the pdf file to process
    :param output_path: path where the output folder is created
    :return: None
    '''
    # checking arguments
    if not pdf_path or not os.path.exists(pdf_path):
        exit('no or faulty pdf file provided')
    if not output_path or not os.path.exists(output_path):
        output_path = os.getcwd()
        print('no or faulty output path provided, using cwd')
    # infer the rest of the needed filepaths
    pdf_name = os.path.basename(pdf_path)
    fname = os.path.splitext(pdf_name)[0]
    output_path = os.path.join(output_path, fname)
    os.makedirs(output_path, exist_ok=False)
    # set up a config, this could be altered for more flexibility
    config_parser = ConfigParser(extractor_ollama_config)

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
    print('finished')

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
        parse_pdf(pdf_path=args.pdf, output_path=args.output)
        return 0
    except Exception as e:
        print(f"Error during PDF conversion: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
