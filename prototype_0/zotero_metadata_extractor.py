# Python 3.13+
from __future__ import annotations

import json
from dataclasses import dataclass

import argparse
import os
import sys
from pathlib import Path
from pprint import pprint
from typing import Dict, Iterable, List, Optional, Tuple

import yaml
from dotenv import load_dotenv

# SQLAlchemy 2.x style imports
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection, Engine


@dataclass(slots=True)
class PdfInfo:
    pdf_name: str
    pdf_path: str  # directory path containing the PDF


class ZoteroMetadataExtractor:
    """
    Extracts item metadata from a Zotero SQLite database, matches it with files
    in the Zotero storage directory, and writes YAML metadata files.
    """

    def __init__(
        self,
        zotero_folder: str | os.PathLike[str],
        zotero_sqlite_path: str | os.PathLike[str] = None,
        overwrite: bool = True,
    ) -> None:
        self.zotero_storage_path = Path(zotero_folder)
        if not os.path.isdir(self.zotero_storage_path):
            raise FileNotFoundError(f"Zotero storage not found: {self.zotero_storage_path}")
        if not zotero_sqlite_path:
            zotero_sqlite_path = self.zotero_storage_path / "zotero.sqlite"
        self.zotero_sqlite_path = Path(zotero_sqlite_path)
        self.overwrite = overwrite

        self._engine: Optional[Engine] = None
        self._conn: Optional[Connection] = None

    # -------------------------
    # Connection management
    # -------------------------

    def connect(self) -> None:
        if self._conn is not None:
            return
        if not self.zotero_sqlite_path.exists():
            raise FileNotFoundError(f"Zotero database not found: {self.zotero_sqlite_path}")
        self._engine = create_engine(f"sqlite:///{self.zotero_sqlite_path}")
        self._conn = self._engine.connect()

    def close(self) -> None:
        try:
            if self._conn is not None:
                self._conn.close()
        finally:
            self._conn = None
            self._engine = None

    # -------------------------
    # NEW: Database structure helper
    # -------------------------

    def print_database_structure(
        self,
        include_row_counts: bool = False,
        include_foreign_keys: bool = True,
    ) -> None:
        """
        Prints a concise structure of the SQLite database:
        - Tables
        - Columns with type and PK/NOT NULL flags
        - Optional row counts
        - Optional foreign key references
        """
        self.connect()
        try:
            assert self._conn is not None
            # List user tables (skip internal sqlite_* tables)
            tables_sql = text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
            tables = [row.name for row in self._conn.execute(tables_sql)]

            if not tables:
                print(f"(No tables) in {self.zotero_sqlite_path}")
                return

            print(f"Database: {self.zotero_sqlite_path}\n")
            for tname in tables:
                print(f"Table: {tname}")
                # Columns
                cols = list(self._conn.execute(text(f"PRAGMA table_info('{tname}')")))
                for col in cols:
                    # PRAGMA table_info: cid, name, type, notnull, dflt_value, pk
                    nn = " NOT NULL" if col.notnull else ""
                    pk = " PK" if col.pk else ""
                    default = f" DEFAULT {col.dflt_value}" if col.dflt_value is not None else ""
                    print(f"  - {col.name}: {col.type}{nn}{pk}{default}")

                # Row count
                if include_row_counts:
                    try:
                        cnt = self._conn.execute(text(f"SELECT COUNT(*) AS c FROM '{tname}'")).scalar_one()
                        print(f"    rows: {cnt}")
                    except Exception:
                        print("    rows: (unavailable)")

                # Foreign keys
                if include_foreign_keys:
                    fks = list(self._conn.execute(text(f"PRAGMA foreign_key_list('{tname}')")))
                    if fks:
                        print("    foreign keys:")
                        for fk in fks:
                            m = fk._mapping  # use mapping interface for name-based access
                            # PRAGMA foreign_key_list: id, seq, table, from, to, on_update, on_delete, match
                            print(
                                f"      * {m['from']} -> {m['table']}({m['to']}) "
                                f"[on_update={m['on_update']}, on_delete={m['on_delete']}]"
                            )
                print()
        finally:
            self.close()

    # -------------------------
    # SQL helpers (parameterized)
    # -------------------------

    def _query_fields_for_item_key(self, item_key: str) -> List[Dict[str, object]]:
        """
        Returns a list of rows where each row has: itemID, fieldName, value.
        Uses fieldsCombined to support both built-in and custom fields.
        """
        assert self._conn is not None, "Database not connected"
        sql = text(
            """
            SELECT
                i.itemID AS itemID,
                fc.fieldName AS fieldName,
                idv.value  AS value
            FROM items AS i
            JOIN itemData AS id        ON id.itemID  = i.itemID
            JOIN fieldsCombined AS fc  ON fc.fieldID = id.fieldID
            JOIN itemDataValues AS idv ON idv.valueID = id.valueID
            WHERE i.key = :item_key;
            """
        )
        result = self._conn.execute(sql, {"item_key": item_key})
        return [dict(row._mapping) for row in result]

    def _query_authors_for_item_key(self, item_key: str) -> List[Tuple[str, str, int]]:
        """
        Returns list of tuples (lastName, firstName, orderIndex) for authors of the item.
        """
        assert self._conn is not None, "Database not connected"
        sql = text(
            """
            SELECT
                c.lastName   AS lastName,
                c.firstName  AS firstName,
                ic.orderIndex AS orderIndex
            FROM items AS i
            JOIN itemCreators AS ic ON ic.itemID = i.itemID
            JOIN creators AS c      ON c.creatorID = ic.creatorID
            WHERE i.key = :item_key
            ORDER BY ic.orderIndex ASC
            """
        )
        result = self._conn.execute(sql, {"item_key": item_key})
        return [(r.lastName or "", r.firstName or "", r.orderIndex or 0) for r in result]

    # New: lookup attachments by basename (pdf file name)
    def _query_parent_items_by_pdf_name(self, pdf_name: str) -> List[Dict[str, object]]:
        """
        Find parent bibliographic items that have an attachment with the given PDF name (case-insensitive).
        Handles both stored attachments (path starting with 'storage:') and linked/absolute paths.
        Returns rows with: parentItemID, parentKey, parentItemTypeID, libraryID, itemTypeName
        """
        assert self._conn is not None, "Database not connected"

        # We match by path ending in '/<pdf_name>' or equals '<pdf_name>' (case-insensitive).
        # This is robust without relying on string reverse (not available in SQLite by default).
        sql = text(
            """
            WITH matches AS (
                SELECT
                    ia.itemID         AS attachmentItemID,
                    ia.parentItemID   AS parentItemID,
                    ia.path           AS path
                FROM itemAttachments AS ia
                WHERE
                    LOWER(ia.path) = LOWER(:name_exact)
                    OR LOWER(ia.path) LIKE LOWER('%/' || :name_exact)
                    OR LOWER(ia.path) LIKE LOWER('storage:%/' || :name_exact)
            )
            SELECT
                p.itemID          AS parentItemID,
                p.key             AS parentKey,
                p.itemTypeID      AS parentItemTypeID,
                p.libraryID       AS libraryID,
                itc.typeName      AS itemTypeName
            FROM matches AS m
            JOIN items AS p            ON p.itemID = m.parentItemID
            JOIN itemTypesCombined AS itc ON itc.itemTypeID = p.itemTypeID
            GROUP BY p.itemID
            """
        )
        result = self._conn.execute(sql, {"name_exact": pdf_name})
        return [dict(row._mapping) for row in result]

    def _query_fields_for_item_id(self, item_id: int) -> Dict[str, object]:
        """
        Returns {fieldName: value} for an item by ID using fieldsCombined.
        """
        assert self._conn is not None, "Database not connected"
        sql = text(
            """
            SELECT
                fc.fieldName AS fieldName,
                idv.value    AS value
            FROM itemData AS id
            JOIN fieldsCombined AS fc  ON fc.fieldID = id.fieldID
            JOIN itemDataValues AS idv ON idv.valueID = id.valueID
            WHERE id.itemID = :item_id
            """
        )
        rows = self._conn.execute(sql, {"item_id": item_id}).fetchall()
        out: Dict[str, object] = {}
        for r in rows:
            out[str(r.fieldName)] = r.value
        return out

    def _query_authors_for_item_id(self, item_id: int) -> List[Tuple[str, str, int]]:
        """
        Returns ordered list of creators (treated as authors for simplicity).
        """
        assert self._conn is not None, "Database not connected"
        sql = text(
            """
            SELECT
                c.lastName   AS lastName,
                c.firstName  AS firstName,
                ic.orderIndex AS orderIndex
            FROM itemCreators AS ic
            JOIN creators AS c ON c.creatorID = ic.creatorID
            WHERE ic.itemID = :item_id
            ORDER BY ic.orderIndex ASC
            """
        )
        result = self._conn.execute(sql, {"item_id": item_id})
        return [(r.lastName or "", r.firstName or "", r.orderIndex or 0) for r in result]

    def _query_tags_for_item_id(self, item_id: int) -> List[str]:
        assert self._conn is not None, "Database not connected"
        sql = text(
            """
            SELECT t.name AS tag
            FROM itemTags AS it
            JOIN tags AS t ON t.tagID = it.tagID
            WHERE it.itemID = :item_id
            ORDER BY t.name
            """
        )
        return [r.tag for r in self._conn.execute(sql, {"item_id": item_id})]

    def _query_collections_for_item_id(self, item_id: int) -> List[Dict[str, object]]:
        """
        Returns list of collections the item belongs to.
        """
        assert self._conn is not None, "Database not connected"
        sql = text(
            """
            SELECT c.collectionID, c.collectionName, c.parentCollectionID
            FROM collectionItems AS ci
            JOIN collections AS c ON c.collectionID = ci.collectionID
            WHERE ci.itemID = :item_id
            ORDER BY c.collectionName
            """
        )
        return [dict(r._mapping) for r in self._conn.execute(sql, {"item_id": item_id})]

    def _query_attachments_for_item_id(self, item_id: int) -> List[Dict[str, object]]:
        """
        Returns attachments for the bibliographic item, not including notes.
        """
        assert self._conn is not None, "Database not connected"
        sql = text(
            """
            SELECT
                ia.itemID        AS attachmentItemID,
                ia.parentItemID  AS parentItemID,
                ia.linkMode,
                ia.contentType,
                ia.charsetID,
                ia.path,
                ia.storageModTime,
                ia.storageHash
            FROM itemAttachments AS ia
            WHERE ia.parentItemID = :item_id
            ORDER BY ia.itemID
            """
        )
        return [dict(r._mapping) for r in self._conn.execute(sql, {"item_id": item_id})]

    def _query_notes_for_item_id(self, item_id: int) -> List[Dict[str, object]]:
        assert self._conn is not None, "Database not connected"
        sql = text(
            """
            SELECT n.itemID AS noteItemID, n.title AS title, n.note AS note
            FROM itemNotes AS n
            WHERE n.parentItemID = :item_id
            ORDER BY n.itemID
            """
        )
        return [dict(r._mapping) for r in self._conn.execute(sql, {"item_id": item_id})]

    def _query_annotation_counts_for_item_id(self, item_id: int) -> Dict[int, int]:
        """
        Returns {attachmentItemID: annotationCount} for each attachment of the item.
        """
        assert self._conn is not None, "Database not connected"
        sql = text(
            """
            SELECT ia.itemID AS attachmentItemID, COUNT(a.itemID) AS annotations
            FROM itemAttachments AS ia
            LEFT JOIN itemAnnotations AS a ON a.parentItemID = ia.itemID
            WHERE ia.parentItemID = :item_id
            GROUP BY ia.itemID
            """
        )
        return {int(r.attachmentItemID): int(r.annotations) for r in self._conn.execute(sql, {"item_id": item_id})}

    # -------------------------
    # Path resolution helpers
    # -------------------------

    def _resolve_attachment_path(self, path: Optional[str]) -> Optional[str]:
        """
        Resolves a Zotero attachment path to a local filesystem path if possible.
        - For stored files: 'storage:ATTACHMENT_KEY/filename.pdf' -> <zotero_storage_path>/ATTACHMENT_KEY/filename.pdf
        - For absolute/linked files: return as-is
        """
        if not path:
            return None
        if path.startswith("storage:"):
            rel = path[len("storage:") :].lstrip("/\\")
            return str(self.zotero_storage_path / rel)
        # Otherwise, it may be absolute or a relative link. We return as-is.
        return path

    @staticmethod
    def _authors_to_string(authors: Iterable[Tuple[str, str, int]]) -> str:
        parts = []
        for last, first, _idx in authors:
            last = (last or "").strip()
            first = (first or "").strip()
            if last and first:
                parts.append(f"{last}, {first}")
            elif last:
                parts.append(last)
            elif first:
                parts.append(first)
        return "; ".join(parts)

    # -------------------------
    # Public API
    # -------------------------

    def create_comprehensive_metadata_from_item_id(self, item_id: int) -> Dict[str, object]:
        """
        Build a comprehensive metadata dictionary for a Zotero item.
        Includes core fields, authors, tags, collections, attachments, notes, and annotation counts.
        """
        assert self._conn is not None, "Database not connected"

        # Basic item info + type
        item_sql = text(
            """
            SELECT i.itemID, i.key, i.itemTypeID, i.libraryID, itc.typeName
            FROM items AS i
            JOIN itemTypesCombined AS itc ON itc.itemTypeID = i.itemTypeID
            WHERE i.itemID = :item_id
            """
        )
        item_row = self._conn.execute(item_sql, {"item_id": item_id}).mappings().first()
        if not item_row:
            return {}

        fields = self._query_fields_for_item_id(item_id)
        authors_list = self._query_authors_for_item_id(item_id)
        authors_str = self._authors_to_string(authors_list)
        tags = self._query_tags_for_item_id(item_id)
        collections = self._query_collections_for_item_id(item_id)
        attachments = self._query_attachments_for_item_id(item_id)
        notes = self._query_notes_for_item_id(item_id)
        ann_counts = self._query_annotation_counts_for_item_id(item_id)

        # Resolve physical paths for attachments
        for att in attachments:
            att["resolvedPath"] = self._resolve_attachment_path(att.get("path"))
            att["annotations"] = ann_counts.get(int(att["attachmentItemID"]), 0)

        # Optionally, compute collection paths (hierarchy) later if needed.

        meta: Dict[str, object] = {
            "id": int(item_row["itemID"]),
            "key": str(item_row["key"]),
            "libraryID": int(item_row["libraryID"]),
            "itemTypeID": int(item_row["itemTypeID"]),
            "itemType": str(item_row["typeName"]),
            "fields": fields,                 # dict: fieldName -> value (e.g., title, date, DOI, etc.)
            "authors": authors_str,           # "Last, First; ..."
            "authorsList": [                  # structured authors with order
                {"lastName": ln, "firstName": fn, "order": idx}
                for (ln, fn, idx) in authors_list
            ],
            "tags": tags,                     # list[str]
            "collections": collections,       # list[ {collectionID, collectionName, parentCollectionID} ]
            "attachments": attachments,       # list[ {attachmentItemID, path, resolvedPath, ...} ]
            "notes": notes,                   # list[ {noteItemID, title, note} ]
        }
        return meta

    def create_comprehensive_metadata_from_pdf_name(self, pdf_name: str) -> List[Dict[str, object]]:
        """
        Given a PDF file name (basename), returns a list of comprehensive metadata dicts for matching items.
        Multiple results may be returned if more than one item has an attachment with the same file name.
        """
        self.connect()
        try:
            matches = self._query_parent_items_by_pdf_name(pdf_name)
            metas: List[Dict[str, object]] = []
            for m in matches:
                meta = self.create_comprehensive_metadata_from_item_id(int(m["parentItemID"]))
                if meta:
                    metas.append(meta)
            return metas
        finally:
            self.close()

    # -------------------------
    # Existing APIs remain; optionally adapt process methods if needed
    # -------------------------

    # -------------------------
    # Metadata assembly
    # -------------------------

    @staticmethod
    def _authors_to_string(authors: Iterable[Tuple[str, str, int]]) -> str:
        parts = []
        for last, first, _idx in authors:
            last = (last or "").strip()
            first = (first or "").strip()
            if last and first:
                parts.append(f"{last}, {first}")
            elif last:
                parts.append(last)
            elif first:
                parts.append(first)
        return "; ".join(parts)

    def create_metadata_dict_from_key(self, item_key: str) -> Optional[Dict[str, object]]:
        """
        Build a metadata dictionary for a Zotero item key.
        Returns None if no fields found for the key.
        """
        fields = self._query_fields_for_item_key(item_key)
        if not fields:
            return None

        # Convert field rows to dict
        meta: Dict[str, object] = {}
        for row in fields:
            field_name = str(row["fieldName"])
            value = row["value"]
            # Prefer the latest occurrence if duplicates happen
            meta[field_name] = value

        # Attach authors
        authors = self._query_authors_for_item_key(item_key)
        meta["authors"] = self._authors_to_string(authors)

        return meta

    # -------------------------
    # Filesystem helpers
    # -------------------------

    @staticmethod
    def _find_first_pdf(dirpath: Path) -> Optional[PdfInfo]:
        if not dirpath.exists() or not dirpath.is_dir():
            return None
        for name in sorted(os.listdir(dirpath)):
            # Strict, case-insensitive extension match
            if name.lower().endswith(".pdf"):
                return PdfInfo(pdf_name=name, pdf_path=str(dirpath))
        return None

    @staticmethod
    def _dir_to_item_key(dirpath: Path) -> str:
        # Zotero storage subdirectory name is the item key
        return dirpath.name

    # -------------------------
    # YAML writer
    # -------------------------

    def write_yaml(self, folder: Path, meta: Dict[str, object]) -> bool:
        """
        Writes meta_data.yaml into 'folder'. Returns True if written or updated,
        False if skipped due to overwrite=False and existing file.
        """
        yaml_path = folder / "meta_data.yaml"
        if yaml_path.exists() and not self.overwrite:
            return False

        # Optional: Remove keys whose values are None to keep YAML compact
        compact_meta = {k: v for k, v in meta.items() if v is not None}

        yaml_path.parent.mkdir(parents=True, exist_ok=True)
        with yaml_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(compact_meta, f, sort_keys=True, allow_unicode=True)
        return True

    # -------------------------
    # Main traversal
    # -------------------------

    def process_library(self) -> None:
        """
        Walk the Zotero storage directory recursively, extract metadata for each subfolder
        with a PDF, and write meta_data.yaml.
        """
        self.connect()
        try:
            for dirpath, dirnames, _filenames in os.walk(self.zotero_storage_path):
                # We only care about leaf subfolders that contain PDFs
                for dirname in dirnames:
                    folder = Path(dirpath) / dirname
                    pdf = self._find_first_pdf(folder)
                    if not pdf:
                        continue

                    item_key = self._dir_to_item_key(folder)
                    meta_raw = self.create_metadata_dict_from_key(item_key)
                    meta_norm = self.parse_zotero_metadata_scico(meta_raw)

                    # Attach PDF info
                    meta_out: Dict[str, object] = {
                        **meta_norm,
                        "pdf_name": pdf.pdf_name,
                        "pdf_path": pdf.pdf_path,
                    }

                    written = self.write_yaml(folder, meta_out)
                    action = "WROTE" if written else "SKIPPED"
                    print(f"{action} YAML for {item_key} at {folder}")
        finally:
            self.close()

    # -------------------------
    # Convenience single-folder method
    # -------------------------

    def process_folder(self, folder: Path) -> Optional[Dict[str, object]]:
        """
        Extracts and writes metadata for a single folder. Returns the written metadata,
        or None if no PDF or no metadata found.
        """
        self.connect()
        try:
            pdf = self._find_first_pdf(folder)
            if not pdf:
                return None

            item_key = self._dir_to_item_key(folder)
            meta_raw = self.create_metadata_dict_from_key(item_key)
            if not meta_raw:
                return None

            meta_norm = self.parse_zotero_metadata_scico(meta_raw)
            meta_out = {**meta_norm, "pdf_name": pdf.pdf_name, "pdf_path": pdf.pdf_path}
            self.write_yaml(folder, meta_out)
            return meta_out
        finally:
            self.close()


def main(argv: Optional[List[str]] = None) -> int:
    load_dotenv()
    extractor = ZoteroMetadataExtractor(
        zotero_folder=os.getenv('ZOTERO_LIBRARY_PATH'),
        zotero_sqlite_path=os.path.join(os.getenv('ZOTERO_LIBRARY_PATH'), 'zotero.sqlite'),
        overwrite=False,
    )

    command = os.getenv('COMMAND', 'extract')


    if command == "db-ls":
        extractor.print_database_structure(
            include_row_counts=True,
            include_foreign_keys=True
        )
        return 0
    
    if command == "meta_from_pdf":
        pdf_info = extractor.create_comprehensive_metadata_from_pdf_name(os.getenv('PDF_NAME'))
        json.dump(pdf_info, sys.stdout, indent=4)
        return 0
        
    if command == "meta_from_key":
        pdf_info = extractor.create_comprehensive_metadata_from_item_id(os.getenv('ITEM_KEY'))
        json.dump(pdf_info, sys.stdout, indent=4)
        return 0

    # Default: extract
    try:
        extractor.process_library()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
