#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ZoteroDatabase.py - A class for interacting with the Zotero SQLite database
"""

import os
from os.path import join, normpath
from collections import defaultdict
from typing import List, Dict, Tuple, Optional, Any

import sqlalchemy
from sqlalchemy import select, distinct
from sqlalchemy.orm import Session
from sqlalchemy.ext.automap import automap_base
from sqlalchemy import Table, Column, Integer, String, DateTime, Boolean, ForeignKey, create_engine
import datetime

class ZoteroDatabase:
    """
    A class to interact with the Zotero SQLite database.
    
    This class provides methods to extract information from Zotero's database,
    such as retrieving metadata, finding PDF paths, and listing items.
    """
    
    def __init__(self, Zotero_path: str):
        """
        Initialize the ZoteroDatabase class.
        
        Args:
            db_path: Path to the Zotero SQLite database file
            storage_path: Path to the Zotero storage directory (where PDFs are stored)
        """
        self.db_path = os.path.join(Zotero_path, 'zotero.sqlite')
        self.storage_path = os.path.join(Zotero_path, 'storage')
        
        # Create SQLAlchemy engine
        self.engine = sqlalchemy.create_engine(f'sqlite:///{self.db_path}')
        
        # Create metadata
        self.metadata = sqlalchemy.MetaData()
        self.metadata.reflect(bind=self.engine)
        
        # Keep reference to relevant tables
        self._setup_zotero_table_references()
        # Set up tracking of the markdown formatted sources for RAG
        self.initialize_conversion_tracking()
    
    def _setup_zotero_table_references(self):
        """Set up direct table references."""
        # Direct table references
        self.items_table = self.metadata.tables['items']
        self.item_attachments_table = self.metadata.tables['itemAttachments']
        self.item_data_values_table = self.metadata.tables['itemDataValues']
        self.item_data_table = self.metadata.tables['itemData']
        self.fields_table = self.metadata.tables['fields']
        self.tags_table = self.metadata.tables['tags']
        self.item_tags_table = self.metadata.tables['itemTags']
        self.item_types_table = self.metadata.tables['itemTypes']

   # ---- Functions to retrieve items and their info ----
    def get_items_that_have_pdfs(self) -> List[Tuple[int, str]]:
        """
        Get all items that have PDF attachments.
        
        Returns:
            List of tuples containing (itemID, title)
        """
        with Session(self.engine) as session:
            stmt = select(distinct(self.items_table.c.itemID), 
                         self.item_data_values_table.c.value) \
                .join(self.item_data_table, 
                      self.items_table.c.itemID == self.item_data_table.c.itemID) \
                .join(self.item_data_values_table, 
                      self.item_data_table.c.valueID == self.item_data_values_table.c.valueID) \
                .join(self.item_attachments_table, 
                      self.item_attachments_table.c.parentItemID == self.items_table.c.itemID) \
                .filter(self.item_data_table.c.fieldID == 1) \
                .filter(self.item_attachments_table.c.contentType == 'application/pdf') \
                .order_by(self.items_table.c.itemID)

            results = session.execute(stmt).all()
            return results
    
    def get_item_metadata(self, item_id: int) -> Dict[str, Any]:
        """
        Get all metadata for a specific item.
        
        Args:
            item_id: The ID of the item to retrieve metadata for
            
        Returns:
            Dictionary of field names and their values
        """
        with Session(self.engine) as session:
            stmt = select(self.item_data_values_table.c.value, 
                         self.fields_table.c.fieldName) \
                .join(self.item_data_table, 
                      self.item_data_values_table.c.valueID == self.item_data_table.c.valueID) \
                .join(self.fields_table, 
                      self.item_data_table.c.fieldID == self.fields_table.c.fieldID) \
                .filter(self.item_data_table.c.itemID == item_id)

            results = session.execute(stmt).all()

            entry_metadata = defaultdict(lambda: "missing")
            for value, field_name in results:
                entry_metadata[field_name] = value

            return dict(entry_metadata)
    
    def get_pdf_path(self, item_id: int) -> Optional[str]:
        """
        Find the file path to the PDF attachment for a specific item.
        
        Args:
            item_id: The ID of the item to find the PDF for
            
        Returns:
            Full path to the PDF file if found, None otherwise
        """
        if not self.storage_path:
            raise ValueError("Storage path not set. Cannot locate PDF files.")
            
        with Session(self.engine) as session:
            stmt = select(self.item_attachments_table.c.path) \
                .join(self.items_table, 
                      self.item_attachments_table.c.parentItemID == self.items_table.c.itemID) \
                .filter(self.items_table.c.itemID == item_id)

            results = session.execute(stmt)
            
            for path_result in results:
                if not path_result[0]:
                    continue
                    
                # Extract path after the colon
                path = path_result[0].split(':')[1]
                
                # Walk through the storage directory to find the file
                for root, dirs, files in os.walk(self.storage_path):
                    for file in files:
                        if path in file and file.endswith('.pdf'):
                            return normpath(join(root, file))
            
            return None
    
    def get_item_tags(self, item_id: int) -> List[str]:
        """
        Get all tags for a specific item.
        
        Args:
            item_id: The ID of the item to retrieve tags for
            
        Returns:
            List of tag names
        """
        with Session(self.engine) as session:
            stmt = select(self.tags_table.c.name) \
                .join(self.item_tags_table, 
                      self.tags_table.c.tagID == self.item_tags_table.c.tagID) \
                .filter(self.item_tags_table.c.itemID == item_id)

            results = session.execute(stmt).all()
            return [tag[0] for tag in results]
    
    def get_item_type(self, item_id: int) -> Optional[str]:
        """
        Get the type of a specific item.
        
        Args:
            item_id: The ID of the item to retrieve the type for
            
        Returns:
            The type name as a string, or None if not found
        """
        with Session(self.engine) as session:
            stmt = select(self.item_types_table.c.typeName) \
                .join(self.items_table, 
                      self.item_types_table.c.itemTypeID == self.items_table.c.itemTypeID) \
                .filter(self.items_table.c.itemID == item_id)

            result = session.execute(stmt).first()
            return result[0] if result else None

    # ---- Functions to handle conversion into markdown files ----
    def initialize_conversion_tracking(self):
        """
        Initialize a table to track PDF to Markdown conversions.

        This table keeps track of which Zotero items have been converted to markdown,
        where the markdown folder is located, when it was created and last updated.

        The table will be created if it doesn't exist.
        """
        # Make sure we have an engine and metadata
        if not hasattr(self, 'engine') or not hasattr(self, 'metadata'):
            raise RuntimeError("Database connection not initialized")

        # Check if the table already exists
        if 'mdConversions' in self.metadata.tables:
            return

        # Define the conversion tracking table
        self.mdConversions_table = Table(
            'mdConversions',
            self.metadata,
            Column('itemID', Integer, ForeignKey('items.itemID'), primary_key=True, unique=True),
            Column('folderPath', String, nullable=False),
            Column('isConverted', Boolean, default=True),
            Column('createdAt', DateTime, default=datetime.datetime.now),
            Column('updatedAt', DateTime, default=datetime.datetime.now,
                   onupdate=datetime.datetime.now)
        )

        # Create the table in the database
        self.mdConversions_table.create(self.engine, checkfirst=True)

        # Update metadata to include the new table
        self.metadata.reflect(bind=self.engine)

        # Reference the table for future use
        self.mdConversions_table = self.metadata.tables['mdConversions']

        print("Markdown conversion tracking table created successfully.")

    def add_conversion_record(self, item_id: int, folder_path: str) -> bool:
        """
        Add a new conversion record.

        Args:
            item_id: The Zotero item ID
            folder_path: Path to the markdown folder for this item

        Returns:
            True if the record was added successfully, False otherwise
        """
        # Initialize the table if not already done
        if 'mdConversions' not in self.metadata.tables:
            self.initialize_conversion_tracking()

        # Check if the item exists in the Zotero database
        with Session(self.engine) as session:
            item_exists = session.query(self.items_table.c.itemID).filter_by(itemID=item_id).scalar() is not None

            if not item_exists:
                print(f"Error: Item with ID {item_id} does not exist in Zotero database.")
                return False

            # Check if a record for this item already exists
            existing_record = session.query(self.mdConversions_table).filter_by(item_id=item_id).first()

            if existing_record:
                print(f"Error: Conversion record for item ID {item_id} already exists.")
                return False

            # Insert new record
            try:
                now = datetime.datetime.now()
                session.execute(
                    self.mdConversions_table.insert().values(
                        item_id=item_id,
                        folder_path=folder_path,
                        is_converted=True,
                        created_at=now,
                        updated_at=now
                    )
                )
                session.commit()
                print(f"Added conversion record for item ID {item_id} pointing to {folder_path}")
                return True
            except Exception as e:
                session.rollback()
                print(f"Error adding conversion record: {str(e)}")
                return False

    def update_conversion_record(self, item_id: int, folder_path: str = None, is_converted: bool = None) -> bool:
        """
        Update an existing conversion record.

        Args:
            item_id: The Zotero item ID
            folder_path: New path to the markdown folder (optional)
            is_converted: New conversion status (optional)

        Returns:
            True if the record was updated successfully, False otherwise
        """
        if 'mdConversions' not in self.metadata.tables:
            print("Error: Conversion tracking table not initialized.")
            return False

        # Prepare update values
        update_values = {'updated_at': datetime.datetime.now()}
        if folder_path is not None:
            update_values['folder_path'] = folder_path
        if is_converted is not None:
            update_values['is_converted'] = is_converted

        # Update the record
        with Session(self.engine) as session:
            try:
                result = session.execute(
                    self.mdConversions_table.update().
                    where(self.mdConversions_table.c.item_id == item_id).
                    values(**update_values)
                )
                session.commit()

                if result.rowcount == 0:
                    print(f"Error: No conversion record found for item ID {item_id}")
                    return False

                print(f"Updated conversion record for item ID {item_id}")
                return True
            except Exception as e:
                session.rollback()
                print(f"Error updating conversion record: {str(e)}")
                return False

    def delete_conversion_record(self, item_id: int) -> bool:
        """
        Delete a conversion record.

        Args:
            item_id: The Zotero item ID to delete from the tracking table

        Returns:
            True if the record was deleted successfully, False otherwise
        """
        if 'mdConversions' not in self.metadata.tables:
            print("Error: Conversion tracking table not initialized.")
            return False

        with Session(self.engine) as session:
            try:
                result = session.execute(
                    self.mdConversions_table.delete().
                    where(self.mdConversions_table.c.item_id == item_id)
                )
                session.commit()

                if result.rowcount == 0:
                    print(f"Error: No conversion record found for item ID {item_id}")
                    return False

                print(f"Deleted conversion record for item ID {item_id}")
                return True
            except Exception as e:
                session.rollback()
                print(f"Error deleting conversion record: {str(e)}")
                return False

    def get_conversion_status(self, item_id: int = None):
        """
        Get the conversion status for one or all items.

        Args:
            item_id: Optional item ID. If provided, returns just that record.
                    If not provided, returns all conversion records.

        Returns:
            Dictionary or list of dictionaries with conversion information
        """
        if 'mdConversions' not in self.metadata.tables:
            print("Error: Conversion tracking table not initialized.")
            return None

        with Session(self.engine) as session:
            try:
                if item_id is not None:
                    # Query for specific item
                    stmt = select(self.mdConversions_table).where(
                        self.mdConversions_table.c.item_id == item_id
                    )
                    result = session.execute(stmt).first()

                    if not result:
                        return None

                    return {
                        'item_id': result.item_id,
                        'folder_path': result.folder_path,
                        'is_converted': result.is_converted,
                        'created_at': result.created_at,
                        'updated_at': result.updated_at
                    }
                else:
                    # Query for all items
                    stmt = select(self.mdConversions_table)
                    results = session.execute(stmt).all()

                    return [
                        {
                            'item_id': row.item_id,
                            'folder_path': row.folder_path,
                            'is_converted': row.is_converted,
                            'created_at': row.created_at,
                            'updated_at': row.updated_at
                        }
                        for row in results
                    ]
            except Exception as e:
                print(f"Error querying conversion records: {str(e)}")
                return None

    def get_non_converted_items(self):
        """
        Get all items with PDFs that haven't been converted to markdown yet.

        Returns:
            List of tuples containing (itemID, title)
        """
        # Get all items with PDFs
        all_pdf_items = self.get_items_with_pdfs()

        if 'mdConversions' not in self.metadata.tables:
            # If tracking table doesn't exist, all items need conversion
            return all_pdf_items

        with Session(self.engine) as session:
            # Get all converted item IDs
            converted_ids_stmt = select(self.mdConversions_table.c.item_id).where(
                self.mdConversions_table.c.is_converted == True
            )
            converted_ids = [row[0] for row in session.execute(converted_ids_stmt).all()]

            # Filter out already converted items
            non_converted = [(item_id, title) for item_id, title in all_pdf_items
                             if item_id not in converted_ids]

            return non_converted

# Example usage for the new functionality
if __name__ == "__main__":
    # Create a ZoteroDatabase instance
    db = ZoteroDatabase(
        db_path="/home/soenkevl/PycharmProjects/scico/prototype3/zotero_metadata_extractor/zotero.sqlite",
        storage_path="/home/soenkevl/Zotero/storage"
    )

    # Initialize the conversion tracking table if it doesn't exist
    db.initialize_conversion_tracking()

    # Example: Add a new conversion record
    item_id = 5
    folder_path = "/path/to/markdown/folder/item5"
    db.add_conversion_record(item_id, folder_path)

    # Example: Update the record
    db.update_conversion_record(item_id, folder_path="/updated/path/item5")

    # Example: Get conversion status for an item
    status = db.get_conversion_status(item_id)
    if status:
        print(f"Conversion status for item {item_id}:")
        for key, value in status.items():
            print(f"  {key}: {value}")

    # Example: Get all items that need conversion
    items_to_convert = db.get_non_converted_items()
    print(f"\nItems needing conversion: {len(items_to_convert)}")
    for item_id, title in items_to_convert[:5]:  # Show first 5
        print(f"  ID: {item_id}, Title: {title}")

    # Example: Delete a conversion record
    # db.delete_conversion_record(item_id)



# Example usage
if __name__ == "__main__":
    # Create a ZoteroDatabase instance
    db = ZoteroDatabase(
        db_path="/home/soenkevl/PycharmProjects/scico/prototype3/zotero_metadata_extractor/zotero.sqlite",
        storage_path="/home/soenkevl/Zotero/storage"
    )
    
    # Example: Get metadata for item with ID 5
    item_id = 5
    metadata = db.get_item_metadata(item_id)
    print(f"Metadata for item {item_id}:")
    for field, value in metadata.items():
        print(f"  {field}: {value}")
    
    # Example: Find PDF path
    pdf_path = db.get_pdf_path(item_id)
    print(f"PDF path: {pdf_path}")