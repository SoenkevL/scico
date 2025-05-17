"""Manage metadata from various sources"""
import yaml
from pathlib import Path


class MetadataManager:
    """
    Manages document metadata from various sources.
    
    This class handles loading, combining, and providing access to
    metadata from Zotero and document parsing.
    """
    
    def __init__(self):
        """Initialize the metadata manager"""
        pass
        
    @staticmethod
    def load_yaml(path):
        """
        Load YAML file into a dictionary.
        
        Args:
            path: Path to YAML file
            
        Returns:
            dict: Loaded YAML content or None if failed
        """
        try:
            with open(path, 'r', encoding='utf-8') as stream:
                return yaml.safe_load(stream)
        except (yaml.YAMLError, IOError) as e:
            print(f"Error loading YAML file {path}: {e}")
            return None

    @staticmethod
    def save_yaml(data, path):
        """
        Save dictionary to YAML file.
        
        Args:
            data: Dictionary to save
            path: Path to save YAML file
            
        Returns:
            bool: True if successful
        """
        try:
            with open(path, 'w', encoding='utf-8') as outfile:
                yaml.dump(data, outfile, default_flow_style=False)
            return True
        except (yaml.YAMLError, IOError) as e:
            print(f"Error saving YAML file {path}: {e}")
            return False

    @staticmethod
    def combine_metadata(*metadata_dicts):
        """
        Combine multiple metadata dictionaries.
        
        Args:
            *metadata_dicts: Variable number of metadata dictionaries
            
        Returns:
            dict: Combined metadata
        """
        result = {}
        for metadata in metadata_dicts:
            if metadata:
                result.update(metadata)
        return result

    @staticmethod
    def extract_citation_info(metadata):
        """
        Extract citation information from metadata.
        
        Args:
            metadata: Metadata dictionary
            
        Returns:
            dict: Citation information
        """
        return {
            'title': metadata.get('title'),
            'authors': metadata.get('authors'),
            'published': metadata.get('published'),
            'publication': metadata.get('publication'),
            'reference': metadata.get('reference')
        }

    @staticmethod
    def format_citation(metadata, style='apa'):
        """
        Format citation string from metadata.
        
        Args:
            metadata: Metadata dictionary
            style: Citation style
            
        Returns:
            str: Formatted citation
        """
        if not metadata:
            return "Unknown Source"
            
        title = metadata.get('title', 'Untitled')
        authors = metadata.get('authors', 'Unknown Author')
        year = metadata.get('published', 'n.d.')
        
        if isinstance(year, str) and len(year) >= 4:
            year = year[:4]  # Extract just the year
            
        if style == 'apa':
            if authors and title:
                return f"{authors} ({year}). {title}"
            elif title:
                return f"{title} ({year})"
            else:
                return "Unknown Source"
        else:
            return f"{title} - {authors} ({year})"


def main():
    """Test metadata manager functionality"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Test metadata manager functionality")
    parser.add_argument("--yaml", help="Path to YAML file to load")
    
    args = parser.parse_args()
    
    manager = MetadataManager()
    
    if args.yaml:
        data = manager.load_yaml(args.yaml)
        if data:
            print("Loaded metadata:")
            for key, value in data.items():
                print(f"  {key}: {value}")
                
            citation = manager.format_citation(data)
            print(f"\nFormatted citation: {citation}")
        else:
            print("Failed to load metadata")


if __name__ == "__main__":
    main()
