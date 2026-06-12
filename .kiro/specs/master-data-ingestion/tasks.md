# Implementation Plan: Master Data Ingestion

## Overview

This plan implements a structured data extraction pipeline that transforms multi-sheet Excel workbooks (JBD branch master and transactional data) into a typed knowledge graph. The pipeline integrates into the existing `IngestionOrchestrator`, routing Excel files from the "master" department through a new `StructuredDataExtractor` that preserves entity relationships, multi-level unit conversions, business glossary annotations, and temporal context.

## Tasks

- [x] 1. Set up core data models and schema infrastructure
  - [x] 1.1 Create data models and dataclasses for the structured extraction pipeline
    - Create `app/services/ingestion/structured_data_extractor.py` with `ParsedSheet`, `ParsedWorkbook` dataclasses
    - Create `app/services/ingestion/schema_registry.py` with `ColumnDefinition`, `SheetSchema`, `ValidationResult` dataclasses
    - Create `app/services/ingestion/master_data_classifier.py` with `ClassificationResult` dataclass
    - Create `app/services/ingestion/entity_graph_builder.py` with `EntityRecord`, `RelationshipRecord`, `BuildResult` dataclasses
    - Create `app/services/ingestion/unit_conversion_resolver.py` with `ConversionEdge` dataclass
    - Create `app/services/ingestion/business_glossary_annotator.py` with `GlossaryEntry` dataclass
    - Create `app/services/ingestion/temporal_context_linker.py` with `TemporalRelationship` dataclass
    - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 7.1, 8.1_

  - [x] 1.2 Define the Schema Registry with all 7 registered schemas
    - Implement `SchemaRegistry._load_default_schemas()` with complete column definitions for MBarang, MPD, MOutlet, SO, Jual, Beli, Stok
    - Define primary keys, foreign keys, and data_category for each schema
    - Implement `SchemaRegistry.get_schema()` with case-insensitive exact matching
    - _Requirements: 2.1, 2.4, 2.5, 3.4_

  - [x] 1.3 Add database migration for EntityRelationship model extension
    - Add `relationship_type` column (String(64), nullable, indexed) to `entity_relationships` table
    - Add `attributes` column (JSON, nullable) to `entity_relationships` table
    - Create and run Alembic migration
    - _Requirements: 6.1, 6.2, 8.1_

- [x] 2. Implement StructuredDataExtractor
  - [x] 2.1 Implement Excel workbook parsing with multi-sheet support
    - Implement `StructuredDataExtractor.extract()` with file size validation (50 MB limit), sheet limit (50), row limit (100,000), column limit (500)
    - Implement `_parse_sheet()` for individual worksheet parsing with type preservation
    - Implement `_detect_header_row()` to identify header rows vs auto-generate Column_N headers
    - Implement `_infer_data_type()` for column type detection (string, numeric, date)
    - Implement `_deduplicate_headers()` to append numeric suffixes to duplicate column names
    - Handle empty row/column filtering to preserve contiguous data region
    - Raise `FileSizeExceededError` for files > 50 MB, `ExcelParseError` for unreadable files
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

  - [x]* 2.2 Write property tests for StructuredDataExtractor
    - **Property 1: Parsing round-trip (serialization identity)**
    - **Property 2: Header uniqueness after deduplication**
    - **Property 3: Empty row/column filtering preserves data region**
    - **Property 4: Auto-generated headers for numeric-only first rows**
    - **Validates: Requirements 1.2, 1.3, 1.4, 1.6**

  - [x]* 2.3 Write unit tests for StructuredDataExtractor
    - Test file size rejection at 50 MB boundary
    - Test parsing of multi-sheet workbooks with varying data types
    - Test error handling for corrupted/unreadable files
    - Test empty sheet handling
    - _Requirements: 1.1, 1.5, 1.7_

- [x] 3. Implement SchemaRegistry validation and MasterDataClassifier
  - [x] 3.1 Implement SchemaRegistry validation logic
    - Implement `SchemaRegistry.validate()` to check required column presence (case-insensitive)
    - Return `ValidationResult` with missing columns, type mismatches, and warnings
    - Preserve raw values for type-mismatched cells
    - Support partial ingestion when required columns are missing
    - _Requirements: 2.2, 2.3, 2.5, 2.6_

  - [x] 3.2 Implement MasterDataClassifier
    - Implement `MasterDataClassifier.classify()` using schema registry lookup
    - Return "master" for MBarang, MPD, MOutlet; "transactional" for SO, Jual, Beli, Stok; "unregistered" for unknown sheets
    - Attach classification metadata to parsed sheet output
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [x]* 3.3 Write property tests for SchemaRegistry and MasterDataClassifier
    - **Property 5: Schema validation identifies all missing required columns**
    - **Property 6: Unregistered sheets bypass validation and entity creation**
    - **Property 7: Type mismatch detection preserves raw values**
    - **Property 8: Classification correctness for registered sheets**
    - **Validates: Requirements 2.2, 2.3, 2.4, 2.6, 3.1, 3.5, 3.6**

- [x] 4. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Implement EntityGraphBuilder for master entities
  - [x] 5.1 Implement master entity creation and upsert logic
    - Implement `EntityGraphBuilder.build_master_entities()` to create one entity per master record
    - Implement `EntityGraphBuilder.upsert_entity()` with primary key matching for deduplication
    - Map MBarang records to product entities (ID, name, price, vendor, dimensions, company)
    - Map MPD records to supplier entities (code, name, address, city, email, blocked)
    - Map MOutlet records to outlet entities (code, name, type, address, area, contact)
    - Skip records with null/empty primary keys and log warnings
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [x]* 5.2 Write property tests for master entity creation
    - **Property 9: Master entity creation with primary key deduplication**
    - **Property 10: Entity upsert idempotence**
    - **Validates: Requirements 3.2, 4.1, 4.2, 4.3, 4.4, 4.5**

- [x] 6. Implement UnitConversionResolver
  - [x] 6.1 Implement multi-level unit conversion parsing and edge creation
    - Implement `UnitConversionResolver.resolve()` to parse SatB/Berisi1/SatT/Berisi2/SatK fields
    - Create exactly two conversion edges for valid 3-level hierarchies (SatB→SatT, SatT→SatK)
    - Handle single-unit products (all units identical, factors = 1) by setting single-unit attribute
    - Skip conversion edge creation for missing/empty unit fields or invalid factors (zero/negative)
    - Implement `compute_equivalent()` for quantity conversion across unit levels
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x]* 6.2 Write property tests for UnitConversionResolver
    - **Property 11: Unit conversion edge creation (3-level hierarchy)**
    - **Property 12: Unit conversion round-trip**
    - **Property 13: Single-unit products create no conversion edges**
    - **Validates: Requirements 5.1, 5.2, 5.3, 5.4**

- [x] 7. Implement foreign key relationship extraction
  - [x] 7.1 Implement transactional relationship building
    - Implement `EntityGraphBuilder.build_transaction_relationships()` to create relationship edges from transactional records to master entities
    - Create directed edges with correct relationship type labels (sold_to, contains_product, sold_at, sold_by, supplied_by, purchased_from, stock_of)
    - Create exactly one relationship edge per non-null foreign key field per record
    - Implement `EntityGraphBuilder.create_relationship()` for edge persistence
    - _Requirements: 6.1, 6.2, 6.5_

  - [x] 7.2 Implement placeholder entity creation for unresolved foreign keys
    - Implement placeholder entity creation when FK value doesn't match existing master entity
    - Mark placeholders with status "unresolved"
    - Implement `EntityGraphBuilder.resolve_placeholder()` to replace placeholders when master data arrives
    - Preserve all existing relationship edges when resolving placeholders
    - _Requirements: 6.3, 6.4_

  - [x]* 7.3 Write property tests for foreign key relationships
    - **Property 14: Foreign key relationship count invariant**
    - **Property 15: Unresolved foreign keys create placeholder entities**
    - **Property 16: Placeholder resolution preserves relationships**
    - **Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5**

- [x] 8. Implement BusinessGlossaryAnnotator
  - [x] 8.1 Implement glossary annotation logic
    - Implement `BusinessGlossaryAnnotator.annotate()` with exact string matching against glossary keys
    - Attach annotations (code, full_name, language) to matching field values
    - Return empty annotations for non-matching values
    - Include all defined glossary entries (PraSO, SO, J, RJ, NO-SO, SatB, SatT, SatK, CS, BTL, PPN, DPP)
    - _Requirements: 7.1, 7.2, 7.3_

  - [x]* 8.2 Write property test for BusinessGlossaryAnnotator
    - **Property 17: Glossary annotation completeness**
    - **Validates: Requirements 7.2, 7.3**

- [x] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement TemporalContextLinker
  - [x] 10.1 Implement temporal relationship creation
    - Implement `TemporalContextLinker.link_so_conversions()` for PraSO → SO conversion relationships
    - Implement `TemporalContextLinker.link_invoice_fulfillment()` for PraSO → Invoice fulfillment relationships
    - Implement `TemporalContextLinker.link_stock_snapshots()` for stock_as_of relationships
    - Handle NO-SO status by setting conversion_status to "unconverted" and skipping conversion relationship
    - Create placeholder pre-sales order entities for unmatched PraSO_Ref values
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x]* 10.2 Write property tests for TemporalContextLinker
    - **Property 18: Temporal SO conversion linking**
    - **Property 19: NO-SO status prevents conversion relationship**
    - **Property 20: Invoice fulfillment linking**
    - **Property 21: Stock snapshot temporal linking**
    - **Validates: Requirements 8.1, 8.2, 8.4, 8.5**

- [x] 11. Implement EntityChunkGenerator and embedding integration
  - [x] 11.1 Implement entity chunk generation for embeddings
    - Create `app/services/ingestion/entity_chunk_generator.py`
    - Implement `generate_product_chunk()` with ID, name, supplier name, unit of sale, selling price
    - Implement `generate_supplier_chunk()` with code, name, city
    - Implement `generate_outlet_chunk()` with code, name, type, area
    - Implement `generate_transaction_summary()` with period, type, quantity, amount, linked entity names
    - _Requirements: 10.1, 10.2_

  - [x]* 11.2 Write property tests for EntityChunkGenerator
    - **Property 22: Entity chunk contains required attributes**
    - **Property 23: Transactional summary contains required fields**
    - **Validates: Requirements 9.2, 10.1, 10.2**

- [x] 12. Integrate with IngestionOrchestrator pipeline
  - [x] 12.1 Implement orchestrator routing and fallback logic
    - Modify `IngestionOrchestrator` to route files with `department=master` to `StructuredDataExtractor`
    - Implement fallback to `TextExtractor` when `StructuredDataExtractor` raises an exception
    - Ensure validation and deduplication stages execute before structured extraction
    - Wire entity chunks into existing `GraphRAGEngine.extract_entities_and_relationships()`
    - _Requirements: 9.1, 9.3, 9.5, 9.6_

  - [x] 12.2 Implement stage logging and ChromaDB metadata storage
    - Record `IngestionStageLog` entry with sheets_parsed, records_extracted, entities_created, relationships_created
    - Store entity embeddings in ChromaDB with metadata: entity_type, department, source_file, primary_key
    - Handle embedding failures gracefully (log warning, continue processing)
    - _Requirements: 9.4, 10.3, 10.5_

  - [x]* 12.3 Write property test for stage log accuracy
    - **Property 27: Stage log accuracy**
    - **Validates: Requirements 9.4, 11.6**

- [x] 13. Implement incremental update support
  - [x] 13.1 Implement incremental upsert and rollback logic
    - Implement primary key matching for entity updates on re-ingestion
    - Retain existing entities absent from new file (no deletion)
    - Add new transaction relationships without removing previous period data
    - Wrap file ingestion in database transaction for atomic rollback on failure
    - Regenerate embeddings for updated entities
    - Leverage existing content hash deduplication to skip unchanged files
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5_

  - [x]* 13.2 Write property tests for incremental ingestion
    - **Property 24: Incremental ingestion preserves absent entities**
    - **Property 25: Additive transactional ingestion**
    - **Property 26: Failed re-ingestion rollback**
    - **Validates: Requirements 11.1, 11.2, 11.5**

  - [x]* 13.3 Write unit tests for incremental update scenarios
    - Test entity attribute update with embedding regeneration
    - Test relationship preservation when entity attributes change
    - Test rollback on partial failure
    - Test content hash deduplication skips unchanged files
    - _Requirements: 11.1, 11.3, 11.4, 11.5_

- [x] 14. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (27 properties total)
- Unit tests validate specific examples and edge cases
- The project already uses `hypothesis==6.112.1` for property-based testing
- All property tests should be placed in `tests/test_master_data_ingestion_properties.py`
- Unit tests go in `tests/test_master_data_ingestion.py`
- Integration tests go in `tests/test_master_data_ingestion_integration.py`

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "3.1"] },
    { "id": 3, "tasks": ["3.2", "3.3"] },
    { "id": 4, "tasks": ["5.1", "6.1", "8.1"] },
    { "id": 5, "tasks": ["5.2", "6.2", "7.1", "8.2"] },
    { "id": 6, "tasks": ["7.2", "7.3"] },
    { "id": 7, "tasks": ["10.1"] },
    { "id": 8, "tasks": ["10.2", "11.1"] },
    { "id": 9, "tasks": ["11.2", "12.1"] },
    { "id": 10, "tasks": ["12.2", "12.3"] },
    { "id": 11, "tasks": ["13.1"] },
    { "id": 12, "tasks": ["13.2", "13.3"] }
  ]
}
```
