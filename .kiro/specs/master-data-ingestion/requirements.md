# Requirements Document

## Introduction

This feature enables the Executive Copilot AI system to ingest structured Excel master data and transactional data from the JBD branch (FMCG distribution), preserving relational structure, business semantics, multi-level unit conversions, and temporal context. The current text extractor flattens Excel sheets into pipe-separated rows, losing entity relationships and business meaning. This feature introduces a structured data extraction pipeline that transforms multi-sheet Excel workbooks into a knowledge graph the AI copilot can reason about for executive-level insights.

## Glossary

- **Structured_Data_Extractor**: The service responsible for parsing multi-sheet Excel workbooks into typed, relational data structures instead of flat text
- **Schema_Registry**: The component that stores and validates expected column schemas for known master data sheet types (MBarang, MPD, MOutlet, SO, Jual, Beli, Stok)
- **Entity_Graph_Builder**: The service that transforms parsed structured records into knowledge graph entities and explicit relationships
- **Unit_Conversion_Resolver**: The component that interprets multi-level unit hierarchies (e.g., CS → BTL with conversion factors) and stores them as queryable relationships
- **Temporal_Context_Linker**: The service that establishes time-based relationships between transactional records (Sales Orders → Invoices → Stock changes)
- **Business_Glossary_Annotator**: The component that attaches business-domain definitions to coded fields (e.g., "PraSO" = Pre-Sales Order, "J/RJ" = Jual/Retur Jual, "NO-SO" = unconverted pre-sales order)
- **Master_Data_Classifier**: The component that distinguishes master/reference data sheets from transactional data sheets and applies appropriate processing strategies
- **Ingestion_Orchestrator**: The existing pipeline orchestrator that coordinates validation, preprocessing, chunking, and embedding stages
- **Knowledge_Graph**: The entity-relationship graph stored in SQLite (entities, relationships) and ChromaDB (embeddings) that the AI copilot queries
- **Sheet**: A single worksheet tab within an Excel workbook file
- **Foreign_Key_Relationship**: A link between records in different sheets established by shared identifier columns (e.g., Outlet ID in SO sheet referencing custcode in MOutlet sheet)
- **Conversion_Factor**: The numeric multiplier defining how many units of a smaller packaging level fit into one unit of a larger packaging level

## Requirements

### Requirement 1: Structured Excel Parsing

**User Story:** As an executive copilot system, I want to parse multi-sheet Excel workbooks into typed relational structures, so that entity relationships and column semantics are preserved rather than flattened into unstructured text.

#### Acceptance Criteria

1. WHEN an Excel file in the master directory is submitted for ingestion, THE Structured_Data_Extractor SHALL parse each sheet independently (up to 50 sheets, up to 100,000 rows and 500 columns per sheet) and produce a typed record set per sheet containing column headers and row data with preserved data types (string, numeric, date)
2. WHEN a sheet contains a header row, THE Structured_Data_Extractor SHALL treat the first non-empty row as the header row and use column names as field identifiers for each record, appending a numeric suffix to any duplicate column names to ensure uniqueness
3. IF a sheet contains rows or columns where all cells are blank or contain only whitespace interspersed with data, THEN THE Structured_Data_Extractor SHALL skip those empty rows and columns while preserving all cells that belong to the contiguous rectangular region bounded by the first and last non-empty cells
4. WHEN parsing is complete, THE Structured_Data_Extractor SHALL produce a structured output that can be serialized to JSON and deserialized back to a structure with identical sheet names, column headers, row count, cell values, and data types (round-trip property)
5. IF an Excel file cannot be opened or contains no readable sheets, THEN THE Structured_Data_Extractor SHALL return an error indicating the failure reason and the file path that caused the failure
6. IF a sheet contains data but no identifiable header row (the first non-empty row contains only numeric values), THEN THE Structured_Data_Extractor SHALL assign auto-generated column identifiers (Column_1, Column_2, ...) and treat all rows as data rows
7. IF an Excel file exceeds 50 MB in size, THEN THE Structured_Data_Extractor SHALL reject the file and return an error indicating the size limit has been exceeded

### Requirement 2: Schema Registry and Validation

**User Story:** As a data engineer, I want known sheet types to be validated against expected schemas, so that data quality issues are detected before ingestion into the knowledge graph.

#### Acceptance Criteria

1. THE Schema_Registry SHALL store expected column definitions for each known sheet type: MBarang, MPD, MOutlet, SO, Jual, Beli, Stok, where each column definition includes the column name, a required or optional flag, and the expected data type (string, numeric, or date)
2. WHEN a parsed sheet name matches a registered schema name using case-insensitive exact matching, THE Schema_Registry SHALL validate that all columns marked as required in the schema are present in the parsed output
3. IF one or more required columns are missing from a parsed sheet, THEN THE Schema_Registry SHALL return a validation result listing each missing column by name and proceed with partial ingestion of the columns that are present
4. WHEN a sheet name does not match any registered schema using case-insensitive exact matching, THE Schema_Registry SHALL classify the sheet as "unregistered" and pass the parsed output to the next pipeline stage without column or type validation
5. THE Schema_Registry SHALL define the expected data type as one of exactly three types (string, numeric, date) for each column in a registered schema
6. IF a column value in a parsed sheet does not conform to the expected data type defined in the schema, THEN THE Schema_Registry SHALL flag the value as a type mismatch in the validation result and proceed with ingestion using the raw value as-is

### Requirement 3: Master vs. Transactional Data Classification

**User Story:** As an executive copilot system, I want master data and transactional data to be classified separately, so that reference entities are treated as stable dimensions and transactions are treated as time-bound facts.

#### Acceptance Criteria

1. WHEN a sheet is parsed and its sheet name matches a registered entry in the Schema_Registry, THE Master_Data_Classifier SHALL classify the sheet as either "master" (reference/dimension data) or "transactional" (time-bound fact data) based on the data_category attribute defined in the Schema_Registry for that sheet name
2. WHILE a sheet is classified as "master", THE Entity_Graph_Builder SHALL create one entity node per record with the record primary key (as defined in the Schema_Registry for that sheet type) as the entity identifier
3. WHILE a sheet is classified as "transactional", THE Entity_Graph_Builder SHALL create relationship edges linking transaction records to their referenced master entities via foreign key columns (as defined in the Schema_Registry for that sheet type) rather than creating standalone entity nodes for each transaction row
4. THE Master_Data_Classifier SHALL classify MBarang, MPD, and MOutlet sheets as "master" and SO, Jual, Beli, and Stok sheets as "transactional"
5. IF a parsed sheet name does not match any registered entry in the Schema_Registry, THEN THE Master_Data_Classifier SHALL classify the sheet as "unregistered" and skip entity or relationship creation for that sheet
6. WHEN classification is complete for a sheet, THE Master_Data_Classifier SHALL attach the classification result ("master", "transactional", or "unregistered") as metadata to the parsed sheet output before passing it to downstream pipeline stages

### Requirement 4: Entity Extraction from Master Data

**User Story:** As an executive copilot system, I want each master data record to become a queryable entity in the knowledge graph, so that the AI can answer questions about specific products, outlets, and suppliers.

#### Acceptance Criteria

1. WHEN a MBarang (product) record is parsed, THE Entity_Graph_Builder SHALL create a product entity with entity_type "product" and attributes: ID, name, selling price, vendor code, dimensions (lebar, tinggi, berat, panjang), and company
2. WHEN a MPD (principal distributor) record is parsed, THE Entity_Graph_Builder SHALL create a supplier entity with entity_type "supplier" and attributes: supplier code, name, address, city, email, and blocked status
3. WHEN a MOutlet (outlet/customer) record is parsed, THE Entity_Graph_Builder SHALL create an outlet entity with entity_type "outlet" and attributes: customer code, name, outlet type, address, area, and contact person
4. THE Entity_Graph_Builder SHALL use the primary key field of each master record as the entity normalized_name for deduplication (product ID for MBarang, custcode for MOutlet, suplcode for MPD)
5. IF a master entity with the same primary key already exists in the Knowledge_Graph, THEN THE Entity_Graph_Builder SHALL update the existing entity attributes rather than creating a duplicate
6. IF a master record has a null or empty primary key field, THEN THE Entity_Graph_Builder SHALL skip entity creation for that record and log a warning identifying the sheet name and row number

### Requirement 5: Multi-Level Unit Conversion

**User Story:** As an executive copilot system, I want product unit conversion hierarchies to be stored as explicit relationships, so that the AI can reason about quantities across different packaging levels (cases, bottles, pieces).

#### Acceptance Criteria

1. WHEN a MBarang record contains multi-level unit fields (SatB, Berisi1, SatT, Berisi2, SatK), THE Unit_Conversion_Resolver SHALL parse the 3-level unit hierarchy and create exactly two conversion relationship edges: one from SatB (big unit) to SatT (medium unit) using Berisi1 as the conversion factor, and one from SatT (medium unit) to SatK (small unit) using Berisi2 as the conversion factor
2. THE Unit_Conversion_Resolver SHALL store each conversion as a relationship edge linked to the product entity with attributes: from_unit, to_unit, and conversion_factor, where conversion_factor is a positive numeric value greater than or equal to 1 representing how many to_unit items fit in one from_unit
3. WHEN a transaction references a product quantity in a specific unit, THE Unit_Conversion_Resolver SHALL compute the equivalent quantity at any other unit level by traversing the stored conversion edges and multiplying or dividing by the conversion factors along the path
4. IF a product record has identical unit names across all levels and all conversion factors equal 1 (e.g., CS → CS → CS with factors 1 and 1), THEN THE Unit_Conversion_Resolver SHALL store a single-unit attribute on the product entity indicating the product uses only one packaging level, and SHALL NOT create conversion relationship edges
5. IF a MBarang record has missing or empty unit fields (SatB, SatT, or SatK) or contains a conversion factor of zero or a negative value, THEN THE Unit_Conversion_Resolver SHALL skip conversion edge creation for that product and log a warning identifying the product ID and the invalid field

### Requirement 6: Foreign Key Relationship Extraction

**User Story:** As an executive copilot system, I want cross-sheet references to be stored as explicit graph relationships, so that the AI can traverse from transactions to their related master entities.

#### Acceptance Criteria

1. THE Entity_Graph_Builder SHALL detect and create relationships for the following foreign key links with the specified relationship type labels: SO.Outlet_ID → MOutlet.custcode (type: "sold_to"), SO.SKU_ID → MBarang.ID (type: "contains_product"), Jual.Outlet_ID → MOutlet.custcode (type: "sold_at"), Jual.SKU → MBarang.ID (type: "contains_product"), Jual.Sales_ID → Salesman entity (type: "sold_by"), Jual.PrincID → MPD.suplcode (type: "supplied_by"), Beli.Principal → MPD.suplcode (type: "purchased_from"), Beli.SKU → MBarang.ID (type: "contains_product"), Stok.Itemcode → MBarang.ID (type: "stock_of")
2. WHEN a transactional record references a master entity by foreign key, THE Entity_Graph_Builder SHALL create a directed relationship edge from the transactional record node to the referenced master entity node, using the relationship type label defined in criterion 1
3. IF a foreign key value in a transactional record does not match any existing master entity, THEN THE Entity_Graph_Builder SHALL log a warning containing the sheet name, row identifier, foreign key field name, and unmatched value, and create a placeholder entity of the expected target type marked with status "unresolved"
4. IF a master entity is ingested whose primary key matches the key of an existing placeholder entity marked as "unresolved", THEN THE Entity_Graph_Builder SHALL replace the placeholder with the fully-populated master entity and retain all existing relationship edges that reference it
5. THE Entity_Graph_Builder SHALL create exactly one relationship edge per foreign key field per transactional record row, resulting in a maximum number of relationship edges per record equal to the number of non-null foreign key fields present in that record

### Requirement 7: Business Glossary Annotation

**User Story:** As an executive copilot system, I want coded field values and abbreviations to be annotated with their business meanings, so that the AI can explain domain terminology to executives.

#### Acceptance Criteria

1. THE Business_Glossary_Annotator SHALL maintain a mapping of coded field values to their business definitions, including: "PraSO" = Pre-Sales Order, "SO" = Sales Order, "J" = Jual (Sales), "RJ" = Retur Jual (Sales Return), "NO-SO" = Pre-Sales Order not converted to Sales Order, "SatB" = Satuan Besar (Big Unit), "SatT" = Satuan Tengah (Medium Unit), "SatK" = Satuan Kecil (Small Unit), "CS" = Case, "BTL" = Bottle, "PPN" = Pajak Pertambahan Nilai (Value Added Tax), "DPP" = Dasar Pengenaan Pajak (Tax Base)
2. WHEN an entity or relationship is created from a record containing one or more field values that match a glossary key by exact string comparison, THE Business_Glossary_Annotator SHALL attach the corresponding business definition to each matched field as a metadata property on the entity or relationship, including the original code, the full business name, and the language of origin
3. IF a record contains a field value that does not match any glossary key, THEN THE Business_Glossary_Annotator SHALL create the entity or relationship without a glossary annotation for that field and SHALL flag the unrecognized value in a processing log
4. WHEN the AI copilot retrieves an entity or relationship that has glossary annotations, THE Business_Glossary_Annotator SHALL include the business definitions as structured metadata fields alongside the entity or relationship data, so that the copilot can reference them in response generation

### Requirement 8: Temporal Context Linking

**User Story:** As an executive copilot system, I want time-based relationships between transactions to be explicit, so that the AI can reason about sales pipelines (PraSO → SO → Invoice) and inventory changes over time.

#### Acceptance Criteria

1. WHEN SO records contain both PraSO dates and SO dates, THE Temporal_Context_Linker SHALL create a "converted_to_so" relationship from the pre-sales order entity to the corresponding sales order entity, matched using the PraSO_Code and SO_No fields, with the PraSO date and SO date stored as relationship attributes
2. WHEN Jual records contain a PraSO_Ref field, THE Temporal_Context_Linker SHALL create a "fulfilled_by" relationship from the originating pre-sales order entity to the invoice entity, matched using the PraSO_Ref value as the pre-sales order identifier
3. IF a Jual record's PraSO_Ref value does not match any existing pre-sales order entity in the Knowledge_Graph, THEN THE Temporal_Context_Linker SHALL log a warning and create a placeholder pre-sales order entity marked as "unresolved" with the "fulfilled_by" relationship still created
4. WHEN Stok records have a timestamp, THE Temporal_Context_Linker SHALL create "stock_as_of" relationships from the stock snapshot to each product entity identified by the Stok.Itemcode field, with the timestamp stored as a relationship attribute
5. WHEN SO records have status "NO-SO", THE Temporal_Context_Linker SHALL set the "conversion_status" attribute of the corresponding pre-sales order entity to "unconverted" and create no forward "converted_to_so" relationship to a sales order

### Requirement 9: Integration with Existing Ingestion Pipeline

**User Story:** As a system architect, I want the structured data extraction to integrate with the existing ingestion pipeline stages, so that master data benefits from existing validation, deduplication, and embedding infrastructure.

#### Acceptance Criteria

1. WHEN an Excel file enters the Ingestion_Orchestrator with a department value of "master" or a subfolder matching a registered Schema_Registry sheet type, THE Ingestion_Orchestrator SHALL route the file to the Structured_Data_Extractor in place of the flat TextExtractor during the preprocessing stage
2. THE Structured_Data_Extractor SHALL produce one chunk per entity, where each chunk contains a natural language description of the entity and its immediate relationships, formatted as plain text consumable by the existing embedding stage
3. WHEN structured entities are produced, THE Ingestion_Orchestrator SHALL pass the entity chunks to the existing GraphRAG engine's extract_entities_and_relationships method for entity persistence and relationship creation in the Knowledge_Graph
4. WHEN the structured extraction stage completes, THE Ingestion_Orchestrator SHALL record an IngestionStageLog entry with a details JSON object containing: sheets_parsed (integer count), records_extracted (integer count), entities_created (integer count), and relationships_created (integer count)
5. IF the Structured_Data_Extractor raises an exception for a file, THEN THE Ingestion_Orchestrator SHALL fall back to the existing flat TextExtractor for that file, log a warning indicating the file name and failure reason, and continue the pipeline using the flat text output
6. THE Ingestion_Orchestrator SHALL execute the existing validation and deduplication stages before routing to the Structured_Data_Extractor, so that schema validation and content hash deduplication apply to structured files

### Requirement 10: Embedding and Retrieval of Structured Entities

**User Story:** As an executive copilot system, I want structured entities to be embedded in a way that preserves their business context, so that semantic search returns relevant master data when executives ask questions about products, outlets, or sales performance.

#### Acceptance Criteria

1. WHEN a master entity is created, THE Ingestion_Orchestrator SHALL generate an embedding from a natural language description of the entity that includes: for product entities — ID, name, supplier name, unit of sale, and selling price; for supplier entities — supplier code, name, and city; for outlet entities — customer code, name, outlet type, and area (e.g., "Fortune Margarine 15k is a product supplied by SARI AGROTAMA PERSADA D, sold in cases at price 182680.77")
2. WHEN a transactional summary is created, THE Ingestion_Orchestrator SHALL generate an embedding from a natural language summary that includes the transaction period (month and year), transaction type (SO, Jual, Beli, or Stok), total quantity, total monetary amount, and the names of linked master entities (product, outlet, or supplier)
3. THE Ingestion_Orchestrator SHALL store entity embeddings in ChromaDB with metadata tags including: entity_type, department ("master"), source_file, and primary_key
4. WHEN the AI copilot performs a retrieval query, THE retrieval service SHALL return the top 10 matching entity embeddings that meet a minimum similarity score of 0.5, along with each result's 1-hop graph neighborhood (all entities and relationships directly connected by a single edge) for context enrichment
5. IF embedding generation fails for an entity, THEN THE Ingestion_Orchestrator SHALL log a warning identifying the entity by primary key and continue processing remaining entities without aborting the ingestion job

### Requirement 11: Incremental Update Support

**User Story:** As a data engineer, I want updated master data files to be re-ingested without duplicating entities, so that the knowledge graph stays current as business data changes monthly.

#### Acceptance Criteria

1. WHEN a master data file is re-ingested with updated content, THE Entity_Graph_Builder SHALL match each parsed record to existing entities by primary key and update changed attributes on matching entities, create new entities for records with unmatched primary keys, and retain existing entities whose primary keys are absent from the new file without deletion
2. WHEN a transactional data file for a new period is ingested, THE Entity_Graph_Builder SHALL add new transaction relationships without removing previous period data, identifying period boundaries by the source file identity
3. THE Ingestion_Orchestrator SHALL use the existing content hash deduplication to skip files that have not changed since last ingestion
4. WHEN an entity attribute changes between ingestion runs, THE Entity_Graph_Builder SHALL update the entity record, regenerate its embedding to reflect the new attribute values, and preserve all existing relationships linked to that entity unless the relationship foreign key itself has changed
5. IF re-ingestion of a file fails after partial processing, THEN THE Entity_Graph_Builder SHALL discard all entity and relationship changes from that file, leaving the Knowledge_Graph in its pre-ingestion state for that file
6. WHEN incremental ingestion completes for a file, THE Ingestion_Orchestrator SHALL record in the stage log the counts of entities created, entities updated, relationships added, and relationships removed
