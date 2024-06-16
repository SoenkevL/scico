import os.path
import sqlite3
import pandas as pd
import yaml
from icecream import ic
import argparse

class ZoteroMetadataExtractor:

    def __init__(self, zotero_library_path, zotero_sqlite_path=None, overwrite=True):
        self.zotero_library_path = zotero_library_path
        self.zotero_sqlite_path = zotero_sqlite_path if zotero_sqlite_path else 'zotero.sqlite'
        self.connz = None # will be used to optimize the code to only load the connection once
        self.overwrite = overwrite # always create new entry if true else skip if metadata exists
        # possible add more placeholder variables if I see need later

    def extract_authors(self, connz):
        df_item_creators = pd.read_sql_query('SELECT * FROM itemCreators', connz)
        df_creators = pd.read_sql_query('SELECT * FROM creators', connz)
        df_combined = pd.merge(df_item_creators, df_creators, on='creatorID')
        itemIDs = []
        authors = []
        for itemID, df in df_combined.groupby('itemID'):
            df = df.sort_values(by='orderIndex')
            res = df.apply(lambda x: f'{x.lastName}, {x.firstName}', axis=1).to_numpy()
            res = ';'.join(res)
            itemIDs.append(itemID)
            authors.append(res)
        author_df = pd.DataFrame(data={'itemID':itemIDs, 'authors':authors})
        return author_df


    def createValueFrame(self, itemID, con):
        return pd.read_sql_query(f"""
            SELECT
            i.itemID,
            idv.value,
            f.fieldName,
            i.key
            FROM itemDataValues AS idv
            JOIN itemData as id ON idv.valueID=id.valueID
            JOIN items as i ON id.itemID=i.itemID
            JOIN fields as f ON id.fieldID=f.fieldID
            WHERE i.itemID=={itemID}
        """, con)


    def createMatchFrame(self, key, con):
        return pd.read_sql_query(f"""
            SELECT
            c.collectionID,
            i.itemID as 'i.itemID',
            ia.parentItemID,
            i.key,
            idv.value as 'fieldValue',
            fc.fieldName
            FROM collections AS c
            JOIN collectionItems as ci ON c.collectioniD=ci.collectionID
            JOIN itemAttachments as ia ON ia.parentItemID=ci.itemID
            JOIN items as i ON i.itemID=ia.itemID
            JOIN itemData as id ON id.itemID=i.itemID
            JOIN itemDataValues as idv ON idv.valueID=id.valueID
            JOIN fieldsCombined as fc ON id.fieldID=fc.fieldID
            WHERE i.key=='{key}'
        """, con)


    def extractItemIDFromMF(self, mf):
        return mf.iloc[0,2]


    def key_extractor(self, path):
        return path.split(os.sep)[-1]


    def createZoteroSql(self,dirname, con):
        try:
            #get item key from dirname
            mf = self.createMatchFrame(dirname, con)
            itemKey = self.extractItemIDFromMF(mf)
            #get values based on item key
            vf = self.createValueFrame(itemKey, con)
            df_authors = self.extract_authors(con)
            df_combined_4 = pd.merge(vf, df_authors, on='itemID')
            #only keep relevant columns
            df_combined_short = df_combined_4.loc[:, ['itemID', 'value', 'fieldName', 'authors']]
            return df_combined_short
        except IndexError:
            return pd.DataFrame(columns=['itemID', 'value', 'fieldName', 'authors'])


    def create_metadata_dict_from_df(self, df):
        array = df.loc[:,['fieldName', 'value']].to_numpy()
        metadata_dict = {f:v for f,v in array}
        metadata_dict['authors']=df.loc[0,'authors']
        return metadata_dict


    def extract_zotero_metadata_to_dictionary(self, path):
        with sqlite3.connect(self.zotero_sqlite_path) as connz:
            dirname = ic(self.key_extractor(path))
            df_db = self.createZoteroSql(dirname, connz)
            if not df_db.empty:
                metadata_dict = self.create_metadata_dict_from_df(df_db)
                return metadata_dict
        return None



    def parse_zotero_metadata_for_paperai(self, metadata_dict):
        title, published, publication, authors, affiliations, affiliation, reference = (
            None,
            None,
            None,
            None,
            None,
            None,
            None
        )
        for key, item in metadata_dict.items():
            if key=='title':
                title=item
            elif key=='date':
                published=item
            elif key=='authors':
                authors=item
            elif key=='publicationTitle':
                publication=item
            elif key=='DOI':
                reference=f'https://doi.org/{item}'

        return (title, published, publication, authors, affiliations, affiliation, reference)

    def parse_zotero_metadata_scico(self, metadata_dict):
        title, published, publication, authors, reference = (
            None,
            None,
            None,
            None,
            None
        )
        if metadata_dict:
            for key, item in metadata_dict.items():
                if key == 'title':
                    title = item
                elif key == 'date':
                    published = item
                elif key == 'authors':
                    authors = item
                elif key == 'publicationTitle':
                    publication = item
                elif key == 'DOI':
                    reference = item

        return {'title':title, 'published':published, 'publication':publication, 'authors':authors, 'reference':reference}

    def meta_dict_to_yaml(self, path, meta_dict):
        yaml_file_name = 'meta_data.yaml'
        full_file_path = os.path.join(path, yaml_file_name)
        if self.overwrite or not os.path.exists(full_file_path):
            with open(full_file_path, 'w') as outfile:
                yaml.dump(meta_dict, outfile, default_flow_style=False)
        empty = 0 if None in meta_dict.keys() else 1
        return empty

    def run_through_dictionary(self):
        direc = self.zotero_library_path
        for root, dirs, files in os.walk(direc):
            for dir in dirs:
                dirpath = ic(os.path.join(root, dir))
                pdf_info = self.pdf_info(dirpath)
                if pdf_info:
                    meta_dict = self.extract_zotero_metadata_to_dictionary(dirpath)
                    meta_dict = self.parse_zotero_metadata_scico(meta_dict)
                    meta_dict = {**meta_dict, **pdf_info}
                    self.meta_dict_to_yaml(dirpath, meta_dict)

    def pdf_info(self, dirpath):
        for file in os.listdir(dirpath):
            if '.pdf' in file:
                pdf_name = file
                pdf_path = dirpath
                return {'pdf_name': pdf_name, 'pdf_path': pdf_path}
        return None


if __name__ == '__main__':
    ic.enable()
    ic('main')
    parser = argparse.ArgumentParser()
    parser.add_argument("-dp", "--database_path", help="path of the zotero database zotero.sqlite")
    parser.add_argument("-sp", "--storage_path", help="zotero storage datapath")
    args = parser.parse_args()
    extractor = ZoteroMetadataExtractor(args.storage_path, args.database_path)
    ic(extractor.zotero_library_path)
    extractor.run_through_dictionary()


