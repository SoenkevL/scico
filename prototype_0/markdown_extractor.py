import os
from icecream import ic
import argparse



class MarkdownExtractor:

    def __init__(self, language='English', batch_multiplier=2, max_pages=100):
        #default parameters for pdf extraction
        self.language = language
        self.batch_multiplier = batch_multiplier
        self.max_pages = max_pages
        pass


    def call_mardown_extractor_on_pdf(self, pdf_path, language=None, batch_multiplier=None, max_pages=None):
        language = language if language else self.language
        batch_multiplier = batch_multiplier if batch_multiplier else self.batch_multiplier
        max_pages = max_pages if max_pages else self.max_pages
        if str(pdf_path).endswith('.pdf'):
            dir_path = os.path.split(pdf_path)[0]
        else:
            dir_path = pdf_path
            for file in os.listdir(dir_path):
                if file.endswith('.pdf'):
                    pdf_path = os.path.join(dir_path, file)
        cmd = f"""
        marker_single '{pdf_path}' '{dir_path}' --batch_multiplier {batch_multiplier} --max_pages {max_pages} --langs {language}
        """
        os.system(cmd)
        return True


    def check_if_markdown_exists(self, path):
        for root, dirs, files in os.walk(path):
            for file in files:
                if '.md' in file:
                    return True
        return False

    def run_through_library(self, library_path, overwrite=False):
        direc = library_path
        for root, dirs, files in os.walk(direc):
            for dir in dirs:
                dirpath = os.path.join(root, dir)
                ic(f'processing dirpath: {dirpath}')
                if not self.check_if_markdown_exists(dirpath) or overwrite:
                    ic(self.call_mardown_extractor_on_pdf(dirpath))
        ic('finished execution of mardown extraction')


if __name__ == '__main__':
    ic.enable()
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--path", help="path of the zotero storage")
    args = parser.parse_args()
    path = args.path
    ic(f'starting extraction of {path}')
    extractor = MarkdownExtractor()
    extractor.run_through_library(path)
