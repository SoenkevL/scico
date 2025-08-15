"""
Zotero SQLite integration via SQLAlchemy.

This module provides a ZoteroMetadataRetriever class that:
    - Connects to a zotero.sqlite database using SQLAlchemy
- Reflects/maps the database schema to Python classes
- Retrieves metadata for a given PDF file path

Notes:
- The schema is reflected dynamically; no hardcoded table models are required.
- The implementation prioritizes common Zotero structures:
- itemAttachments: stores attachment records (including file path)
- items: base table for items
    - itemData + itemDataValues + fields: stores per-field metadata (title, date, DOI, url, etc.)
- itemCreators + creators + creatorTypes: authors and their roles
- itemTags + tags: user tags
- collectionItems + collections: collections membership
- The function attempts to match the given PDF path in several ways (exact match, filename match, and LIKE patterns).
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from dotenv import load_dotenv
from sqlalchemy import create_engine, select, func
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, registry, aliased


@dataclass
class ZoteroConnectionConfig:
    """
    Configuration for connecting to a Zotero SQLite database.

    Attributes:
    sqlite_path: Absolute path to the zotero.sqlite file.
    """
    zotero_path: Path
    sqlite_path: Optional[Path] = None

    def sqlalchemy_url(self) -> str:
        # Use pysqlite driver which is included in Python's stdlib for SQLite
        # Ensure path is absolute to avoid working-directory surprises
        self.sqlite_path = Path(os.path.join(self.zotero_path, "zotero.sqlite"))
        abs_str = str(self.sqlite_path.expanduser().resolve())
        return f"sqlite+pysqlite:///{abs_str}"


class ZoteroMetadataRetriever:
    """
    Connects to a Zotero SQLite database, reflects the schema, and retrieves metadata
    for a given PDF file path.

    Typical usage:
    retriever = ZoteroMetadataRetriever(Path("/path/to/zotero.sqlite"))
    retriever.initialize()
    data = retriever.get_metadata_for_pdf(Path("/path/to/storage/ABCD1234/paper.pdf"))
    print(data)
    """

    def __init__(self, zotero_path: Path) -> None:
        self.config = ZoteroConnectionConfig(zotero_path=zotero_path)
        self._engine: Optional[Engine] = None
        self._mapper_registry: Optional[registry] = None

        # Reflected mapped classes (set in _reflect_schema)
        self.Items = None
        self.ItemAttachments = None
        self.ItemData = None
        self.ItemDataValues = None
        self.Fields = None
        self.ItemCreators = None
        self.Creators = None
        self.CreatorTypes = None
        self.ItemTags = None
        self.Tags = None
        self.CollectionItems = None
        self.Collections = None

    # ---------------------------
    # Public API
    # ---------------------------

    def initialize(self) -> None:
        """
        Create the engine and reflect/map the schema.
        """
        self._create_engine()
        self._reflect_schema()

    def get_metadata_for_pdf(self, pdf_path: Path) -> Optional[Dict[str, Any]]:
        """
        Retrieve metadata for a given PDF file path.

        Strategy:
        - Find attachment items (itemAttachments) whose 'path' matches the given path in a few ways:
        1) Exact match against stored path (as-is and POSIX form)
        2) Exact match by filename only (to handle storage path differences)
        3) LIKE-based suffix match on filename (fallback)
                                      - For each matched attachment, find the parent item (bibliographic item).
        - Assemble metadata including: title, creators, year, DOI, URL, abstract, publication title,
        tags, collections, and some attachment details.

        Returns:
        A dictionary with metadata if found, else None. If multiple items match, returns
        the first best match (exact > filename > LIKE).
        """
        self._ensure_initialized()

        attachment_rows = []
        with self._session() as ses:
            ItemAttachments = self.ItemAttachments

            # Normalize search inputs
            pdf_path_str = str(pdf_path)
            pdf_path_posix = pdf_path.as_posix()
            filename = pdf_path.name

            # 1) Exact path match
            exact_q = (
                select(ItemAttachments)
                .where(
                    (ItemAttachments.path == pdf_path_str)
                    | (ItemAttachments.path == pdf_path_posix)
                )
            )
            attachment_rows = list(ses.execute(exact_q).scalars().all())

            # 2) Fallback: exact filename match in path (common when Zotero stores 'storage:HASH/file.pdf')
            if not attachment_rows:
                attachment_rows = list(
                    ses.execute(
                        select(ItemAttachments).where(
                            func.lower(func.substr(ItemAttachments.path, -len(filename))) == filename.lower()
                        )
                    ).scalars().all()
                )

            # 3) Fallback: LIKE-based pattern match on filename
            if not attachment_rows:
                like_pattern = f"%{filename}"
                attachment_rows = list(
                    ses.execute(
                        select(ItemAttachments).where(ItemAttachments.path.like(like_pattern))
                    ).scalars().all()
                )

            if not attachment_rows:
                return None

            # Prefer an attachment that has a parent item (bibliographic record)
            chosen = next((a for a in attachment_rows if getattr(a, "parentItemID", None)), attachment_rows[0])

            parent_item_id = getattr(chosen, "parentItemID", None)
            # If there's no parent (standalone attachment), try to use its own itemID as base
            base_item_id = parent_item_id or getattr(chosen, "itemID", None)
            if base_item_id is None:
                return None

            # Assemble metadata dict
            metadata = self._build_metadata_for_item(ses, base_item_id)

            # Include attachment-specific properties
            metadata["attachment"] = {
                "attachment_item_id": getattr(chosen, "itemID", None),
                "parent_item_id": getattr(chosen, "parentItemID", None),
                "path": getattr(chosen, "path", None),
                "content_type": getattr(chosen, "contentType", None),
                "charset_id": getattr(chosen, "charsetID", None),
                "storage_mod_time": getattr(chosen, "mtime", None),
            }

            return metadata

    # ---------------------------
    # Internal helpers
    # ---------------------------

    def _create_engine(self) -> None:
        if self._engine is not None:
            return
        url = self.config.sqlalchemy_url()
        # Future-style engine; SQLite pragma optimizations can be set if needed
        self._engine = create_engine(url, future=True)

    # Fix _reflect_schema to use SQLAlchemy automap, compatible with SQLAlchemy 2.x
    def _reflect_schema(self) -> None:
        if self._mapper_registry is not None:
            return

        # Use automap to reflect and prepare mapped classes
        from sqlalchemy.ext.automap import automap_base

        assert self._engine is not None, "Engine must be created before reflecting schema."
        Base = automap_base()
        # Prepare automap with the existing engine; reflect all tables
        Base.prepare(autoload_with=self._engine)

        # Keep a reference so we know we're initialized
        # We keep the name _mapper_registry for minimal impact, but it now holds the automap Base
        self._mapper_registry = Base

        # Bind commonly used tables to attributes for convenience
        # These names must match the SQLite table names.
        self.Items = Base.classes.items
        self.ItemAttachments = Base.classes.itemAttachments
        self.ItemData = Base.classes.itemData
        self.ItemDataValues = Base.classes.itemDataValues
        self.Fields = Base.classes.fields
        self.ItemCreators = Base.classes.itemCreators
        self.Creators = Base.classes.creators
        self.CreatorTypes = Base.classes.creatorTypes
        self.ItemTags = Base.classes.itemTags
        self.Tags = Base.classes.tags
        self.CollectionItems = Base.classes.collectionItems
        self.Collections = Base.classes.collections

    def _ensure_initialized(self) -> None:
        if self._engine is None or self._mapper_registry is None:
            raise RuntimeError("ZoteroMetadataRetriever is not initialized. Call initialize() first.")

    @contextmanager
    def _session(self) -> Iterable[Session]:
        assert self._engine is not None
        ses = Session(self._engine, future=True)
        try:
            yield ses
        except SQLAlchemyError as exc:
            ses.rollback()
            raise exc
        finally:
            ses.close()

    # --------- Metadata assembly ---------

    def _build_metadata_for_item(self, ses: Session, item_id: int) -> Dict[str, Any]:
        """
        Build a rich metadata dictionary for a given bibliographic itemID.
        """
        # Base dictionary with stable keys
        data: Dict[str, Any] = {
            "item_id": item_id,
            "title": None,
            "creators": [],
            "year": None,
            "date": None,
            "publication_title": None,
            "doi": None,
            "url": None,
            "abstract": None,
            "tags": [],
            "collections": [],
        }

        # Field map lookup
        fields = self._get_field_name_to_id_map(ses)
        get_val = lambda field_name: self._get_item_field_value(ses, item_id, fields.get(field_name))

        data["title"] = get_val("title")
        data["date"] = get_val("date")
        data["doi"] = get_val("DOI") or get_val("doi")
        data["url"] = get_val("url")
        data["abstract"] = get_val("abstractNote")
        data["publication_title"] = get_val("publicationTitle") or get_val("journalAbbreviation")

        # Derive year from date if possible
        date_val = data["date"]
        data["year"] = self._extract_year(date_val) if isinstance(date_val, str) else None

        # Creators (authors, editors, etc.)
        data["creators"] = self._get_item_creators(ses, item_id)
        data['authors'] = self._creators_to_string(data['creators'])

        # Tags
        data["tags"] = self._get_item_tags(ses, item_id)

        # Collections
        data["collections"] = self._get_item_collections(ses, item_id)
        data["bibkey"] = self._create_bib_key_from_info(data)

        return data

    def _get_field_name_to_id_map(self, ses: Session) -> Dict[str, int]:
        Fields = self.Fields
        rows = ses.execute(select(Fields.fieldID, Fields.fieldName)).all()
        return {name: fid for fid, name in rows}

    def _get_item_field_value(self, ses: Session, item_id: int, field_id: Optional[int]) -> Optional[str]:
        if field_id is None:
            return None
        ItemData = self.ItemData
        ItemDataValues = self.ItemDataValues

        q = (
            select(ItemDataValues.value)
            .join(ItemData, ItemData.valueID == ItemDataValues.valueID)
            .where((ItemData.itemID == item_id) & (ItemData.fieldID == field_id))
            .limit(1)
        )
        row = ses.execute(q).first()
        return row[0] if row else None

    def _get_item_creators(self, ses: Session, item_id: int) -> List[Dict[str, Any]]:
        ItemCreators = self.ItemCreators
        Creators = self.Creators
        CreatorTypes = self.CreatorTypes

        q = (
            select(
                Creators.lastName,
                Creators.firstName,
                Creators.fieldMode,
                CreatorTypes.creatorType,
                ItemCreators.orderIndex,
            )
            .join(ItemCreators, ItemCreators.creatorID == Creators.creatorID)
            .join(CreatorTypes, CreatorTypes.creatorTypeID == ItemCreators.creatorTypeID)
            .where(ItemCreators.itemID == item_id)
            .order_by(ItemCreators.orderIndex.asc())
        )
        creators: List[Dict[str, Any]] = []
        for ln, fn, field_mode, ctype, idx in ses.execute(q).all():
            # fieldMode==1 often signifies single-field creator (e.g., "Organization")
            if field_mode == 1:
                name = ln or fn
            else:
                name = " ".join(part for part in [fn, ln] if part)
            creators.append(
                {
                    "name": name,
                    "first_name": fn,
                    "last_name": ln,
                    "type": ctype,
                    "order": idx,
                }
            )
        return creators

    @staticmethod
    def _creators_to_string(authors: List[Dict]) -> str:
        parts = []
        for author in authors:
            last = author.get('last_name', '').strip()
            first = author.get('first_name', '').strip()
            if last and first:
                parts.append(f"{last}, {first}")
            elif last:
                parts.append(last)
            elif first:
                parts.append(first)
        return "; ".join(parts)

    def _get_item_tags(self, ses: Session, item_id: int) -> List[str]:
        ItemTags = self.ItemTags
        Tags = self.Tags

        q = (
            select(Tags.name)
            .join(ItemTags, ItemTags.tagID == Tags.tagID)
            .where(ItemTags.itemID == item_id)
            .order_by(Tags.name.asc())
        )
        return [name for (name,) in ses.execute(q).all() if name]

    def _get_item_collections(self, ses: Session, item_id: int) -> List[Dict[str, Any]]:
        CollectionItems = self.CollectionItems
        Collections = self.Collections

        parent_alias = aliased(Collections)

        q = (
            select(
                Collections.collectionID,
                Collections.collectionName,
                Collections.parentCollectionID,
                parent_alias.collectionName,
            )
            .join(CollectionItems, CollectionItems.collectionID == Collections.collectionID)
            .outerjoin(parent_alias, parent_alias.collectionID == Collections.parentCollectionID)
            .where(CollectionItems.itemID == item_id)
            .order_by(Collections.collectionName.asc())
        )
        result: List[Dict[str, Any]] = []
        for cid, cname, parent_id, parent_name in ses.execute(q).all():
            result.append(
                {
                    "collection_id": cid,
                    "name": cname,
                    "parent_collection_id": parent_id,
                    "parent_name": parent_name,
                }
            )
        return result

    @staticmethod
    def _extract_year(date_str: Optional[str]) -> Optional[int]:
        if not date_str:
            return None
        # Basic heuristic: find a 4-digit year
        for token in (date_str, *date_str.replace("/", "-").split("-")):
            token = token.strip()
            if len(token) == 4 and token.isdigit():
                try:
                    year = int(token)
                    if 1000 <= year <= 9999:
                        return year
                except ValueError:
                    pass
        return None

    @staticmethod
    def _create_bib_key_from_info(data: Dict[str, Any]) -> str:
        year = data.get("year", 'nodate')
        title = data.get("title", 'noname ')
        authors = data.get("authors", 'noauthor,')
        title_ident = title.split(' ')[0].lower()
        authors_ident = authors.split(',')[0].lower()
        key = f"{authors_ident}_{title_ident}_{year}"
        return key


# ---------------------------
# Optional: simple CLI entry (for manual testing)
# ---------------------------

def demo_cli() -> None:
    """
    Minimal CLI for quick testing:
        python ZoteroIntegration.py --db /path/to/zotero.sqlite --pdf /path/to/file.pdf
    """
    import json
    import os
    load_dotenv()
    retriever = ZoteroMetadataRetriever(Path(os.getenv("ZOTERO_LIBRARY_PATH")))
    retriever.initialize()
    meta = retriever.get_metadata_for_pdf(Path(os.getenv("TEST_PDF_PATH")))
    if meta is None:
        print("No metadata found for the given PDF path.")
    else:
        print(json.dumps(meta, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    demo_cli()