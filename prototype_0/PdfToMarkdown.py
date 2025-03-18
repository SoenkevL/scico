from marker.converters.pdf import PdfConverter
import argparse
from marker.models import create_model_dict
from marker.config.parser import ConfigParser
from marker.output import text_from_rendered, save_output
import os

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
    # set up a config, this could be altered for more flexibility
    ollama_config = {
        "output_format": "markdown",
        'use_llm': True,
        'llm_service': 'marker.services.ollama.OllamaService',
        'ollama_base_url': 'http://localhost:11434',
        'ollama_model': 'qwen2.5:14b'
    }
    config_parser = ConfigParser(ollama_config)

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

    # Validate output path if provided
    if args.output and not os.path.exists(args.output):
        print(f"Warning: Output directory '{args.output}' does not exist. Attempting to create it.")
        try:
            os.makedirs(args.output)
        except Exception as e:
            print(f"Error creating output directory: {e}")
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
