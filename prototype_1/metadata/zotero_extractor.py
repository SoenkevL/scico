"""Extract metadata from Zotero database and storage"""
import os
import sqlite3
import pandas as pd
import yaml
import argparse
from pathlib import Path


class ZoteroMetadataExtractor:
    """
    Extracts and processes metadata from Zotero library and database.
    
    This class connects to a Zotero SQLite database and extracts relevant
    metadata about documents, including authors, titles, and publication info.
    """
    
    def __init__(self, zotero_library_path, zotero_sqlite_path=None, overwrite=True):
        """
        Initialize the Zotero metadata extractor.
        
        Args:
            zotero_library_path: Path to Zotero storage directory
            zotero_sqlite_path: Path to Zotero SQLite database
            overwrite: Whether to overwrite existing metadata files
        """
        self.zotero_library_path = Path(zotero_library_path)
        self.zotero_sqlite_path = zotero_sqlite_path if zotero_sqlite_path else 'zotero.sqlite'
        self.overwrite = overwrite
        
    def extract_authors(self, connection):
        """
        Extract author information from database.
        
        Args:
            connection: SQLite database connection
            
        Returns:
            DataFrame: Author information by itemID
        """
        # Query creator tables
        df_item_creators = pd.read_sql_query('SELECT * FROM itemCreators', connection)
        df_creators = pd.read_sql_query('SELECT * FROM creators', connection)
        
        # Merge and format author information
        df_combined = pd.merge(df_item_creators, df_creators, on='creatorID')
        
        # Collect and format authors for each item
        item_ids = []
        authors_list = []
        
        for item_id, group in df_combined.groupby('itemID'):
            group = group.sort_values(by='orderIndex')
            formatted_authors = group.apply(lambda x: f'{x.lastName}, {x.firstName}', axis=1).to_numpy()
            authors_string = ';'.join(formatted_authors)
            
            item_ids.append(item_id)
            authors_list.append(authors_string)
            
        # Create author dataframe
        return pd.DataFrame(data={'itemID': item_ids, 'authors': authors_list})
        
    def get_item_metadata(self, item_id, connection):
        """
        Get metadata for a specific item.
        
        Args:
            item_id: Zotero item ID
            connection: SQLite database connection
            
        Returns:
            DataFrame: Item metadata
        """
        query = """
            SELECT
            i.itemID,
            idv.value,
            f.fieldName,
            i.key
            FROM itemDataValues AS idv
            JOIN itemData as id ON idv.valueID=id.valueID
            JOIN items as i ON id.itemID=i.itemID
            JOIN fields as f ON id.fieldID=f.fieldID
            WHERE i.itemID=?
        """
        
        return pd.read_sql_query(query, connection, params=(item_id,))
        
    def find_item_by_key(self, key, connection):
        """
        Find item information by key.
        
        Args:
            key: Zotero item key
            connection: SQLite database connection
            
        Returns:
            DataFrame: Matching item information
        """
        query = """
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
            WHERE i.key=?
        """
        
        return pd.read_sql_query(query, connection, params=(key,))
        
    def extract_parent_item_id(self, match_frame):
        """
        Extract parent item ID from match frame.
        
        Args:
            match_frame: DataFrame from find_item_by_key
            
        Returns:
            int: Parent item ID
        """
        if match_frame.empty:
            raise ValueError("No matching item found")
            
        return match_frame.iloc[0, 2]
        
    def extract_key_from_path(self, path):
        """
        Extract Zotero key from file path.
        
        Args:
            path: Path to item directory
            
        Returns:
            str: Zotero key
        """
        return str(Path(path).name)
        
    def get_item_metadata_by_path(self, path, connection):
        """
        Get item metadata using directory path.
        
        Args:
            path: Path to item directory
            connection: SQLite database connection
            
        Returns:
            DataFrame: Item metadata
        """
        try:
            # Extract key and find matching item
            key = self.extract_key_from_path(path)
            match_frame = self.find_item_by_key(key, connection)
            parent_id = self.extract_parent_item_id(match_frame)
            
            # Get metadata for parent item
            value_frame = self.get_item_metadata(parent_id, connection)
            authors_df = self.extract_authors(connection)
            
            # Combine metadata with author information
            combined_df = pd.merge(value_frame, authors_df, on='itemID')
            
            # Select relevant columns
            return combined_df.loc[:, ['itemID', 'value', 'fieldName', 'authors']]
            
        except (ValueError, IndexError) as e:
            print(f"Error getting metadata for {path}: {e}")
            return pd.DataFrame(columns=['itemID', 'value', 'fieldName', 'authors'])
            
    def create_metadata_dict(self, metadata_df):
        """
        Convert metadata DataFrame to dictionary.
        
        Args:
            metadata_df: DataFrame with metadata
            
        Returns:
            dict: Metadata dictionary
        """
        if metadata_df.empty:
            return {}
            
        # Extract field-value pairs
        field_values = metadata_df.loc[:, ['fieldName', 'value']].to_numpy()
        metadata_dict = {field: value for field, value in field_values}
        
        # Add authors if available
        if not metadata_df.empty and 'authors' in metadata_df.columns:
            metadata_dict['authors'] = metadata_df.loc[0, 'authors']
            
        return metadata_dict
        
    def get_metadata_for_path(self, path):
        """
        Get metadata dictionary for a path.
        
        Args:
            path: Path to item directory
            
        Returns:
            dict: Metadata dictionary
        """
        with sqlite3.connect(self.zotero_sqlite_path) as connection:
            metadata_df = self.get_item_metadata_by_path(path, connection)
            return self.create_metadata_dict(metadata_df)
            
    def parse_metadata(self, metadata_dict):
        """
        Parse and normalize metadata dictionary.
        
        Args:
            metadata_dict: Raw metadata dictionary
            
        Returns:
            dict: Normalized metadata dictionary
        """
        if not metadata_dict:
            return {
                'title': None,
                'published': None,
                'publication': None,
                'authors': None,
                'reference': None
            }
            
        result = {}
        
        # Extract common fields
        result['title'] = metadata_dict.get('title')
        result['published'] = metadata_dict.get('date')
        result['authors'] = metadata_dict.get('authors')
        result['publication'] = metadata_dict.get('publicationTitle')
        result['reference'] = metadata_dict.get('DOI')
        
        return result
        
    def save_metadata_yaml(self, path, metadata_dict):
        """
        Save metadata dictionary as YAML file.
        
        Args:
            path: Directory to save YAML file
            metadata_dict: Metadata dictionary
            
        Returns:
            bool: True if successful
        """
        yaml_path = Path(path) / 'meta_data.yaml'
        
        # Skip if file exists and overwrite is disabled
        if yaml_path.exists() and not self.overwrite:
            return False
            
        try:
            with open(yaml_path, 'w') as outfile:
                yaml.dump(metadata_dict, outfile, default_flow_style=False)
            return True
        except Exception as e:
            print(f"Error saving metadata YAML: {e}")
            return False
            
    def get_pdf_info(self, dir_path):
        """
        Get PDF file information from directory.
        
        Args:
            dir_path: Directory path
            
        Returns:
            dict: PDF filename and path information
        """
        dir_path = Path(dir_path)
        
        for file in os.listdir(dir_path):
            if file.lower().endswith('.pdf'):
                return {
                    'pdf_name': file,
                    'pdf_path': str(dir_path)
                }
                
        return None
        
    def process_library(self):
        """
        Process entire Zotero library to extract metadata.
        
        Returns:
            int: Number of metadata files created
        """
        if not self.zotero_library_path.exists():
            raise ValueError(f"Zotero library path does not exist: {self.zotero_library_path}")
            
        processed_count = 0
        
        # Walk through directory structure
        for root, dirs, files in os.walk(self.zotero_library_path):
            for dir_name in dirs:
                dir_path = Path(root) / dir_name
                
                # Check if directory contains a PDF
                pdf_info = self.get_pdf_info(dir_path)
                if not pdf_info:
                    continue
                    
                # Extract and save metadata
                raw_metadata = self.get_metadata_for_path(dir_path)
                parsed_metadata = self.parse_metadata(raw_metadata)
                
                # Combine with PDF info
                combined_metadata = {**parsed_metadata, **pdf_info}
                
                # Save as YAML
                if self.save_metadata_yaml(dir_path, combined_metadata):
                    processed_count += 1
                    
        print(f"Processed metadata for {processed_count} documents")
        return processed_count


def main():
    """Command-line interface for metadata extraction"""
    parser = argparse.ArgumentParser(description="Extract metadata from Zotero library")
    parser.add_argument("-dp", "--database_path", required=True, 
                        help="Path to Zotero database (zotero.sqlite)")
    parser.add_argument("-sp", "--storage_path", required=True,
                        help="Path to Zotero storage directory")
    parser.add_argument("--no-overwrite", action="store_true",
                        help="Don't overwrite existing metadata files")
    
    args = parser.parse_args()
    
    extractor = ZoteroMetadataExtractor(
        args.storage_path, 
        args.database_path,
        overwrite=not args.no_overwrite
    )
    
    extractor.process_library()


if __name__ == '__main__':
    main()
