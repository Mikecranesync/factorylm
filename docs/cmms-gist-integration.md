# CMMS Gist Integration Guide

FactoryLM generates portable work orders as GitHub Gists. Each Gist contains three files — Markdown (human-readable), CSV (machine-importable), and an attachments manifest. Any major CMMS can import the CSV directly or through its bulk-import tool.

## Why Gists?

- **Version-controlled**: Every edit is tracked
- **Commentable**: Technicians and admins can add notes
- **API-accessible**: `gh gist view`, GitHub REST API, or webhooks
- **No vendor lock-in**: CSV works everywhere; Markdown is readable anywhere
- **Shareable**: Public URL, no login required for viewing

---

## CSV Column Reference

All 25 columns in `work-order.csv`:

| # | Column | Type | Required | Description |
|---|--------|------|----------|-------------|
| 1 | work_order_id | string | yes | FactoryLM ID: `WO-YYYY-MMDD-NNN` |
| 2 | title | string | yes | Short summary of the work |
| 3 | status | string | yes | open, in_progress, completed, cancelled |
| 4 | priority | string | yes | critical, high, medium, low |
| 5 | asset_name | string | yes | Human-readable asset name |
| 6 | asset_id | string | no | Machine-readable asset tag |
| 7 | location | string | no | Physical location within the facility |
| 8 | site | string | no | Plant or facility name |
| 9 | assigned_to | string | no | Technician name |
| 10 | assigned_team | string | no | Maintenance team |
| 11 | work_type | string | no | Corrective, Preventive, Predictive, Emergency |
| 12 | category | string | no | Mechanical, Electrical, Instrumentation, HVAC |
| 13 | due_date | date | no | YYYY-MM-DD |
| 14 | created_date | datetime | no | ISO 8601 |
| 15 | completed_date | datetime | no | ISO 8601 or empty |
| 16 | completed_by | string | no | Technician who completed the work |
| 17 | reported_by | string | no | Who reported the issue |
| 18 | channel | string | no | Telegram, WhatsApp, Phone, Slack |
| 19 | estimated_hours | decimal | no | Estimated labor hours |
| 20 | cost | decimal | no | Estimated or actual cost |
| 21 | completion_notes | string | no | Free text notes on work performed |
| 22 | failure_code | string | no | Standardized failure code |
| 23 | description | string | no | Detailed description of the issue |
| 24 | cmms_system | string | no | Target CMMS for import |
| 25 | cmms_external_id | string | no | ID in the target CMMS after import |

---

## Per-CMMS Mapping Tables

### 1. IBM Maximo (MIF — Maximo Integration Framework)

Import method: CSV upload or MIF XML inbound channel.

| FactoryLM Column | Maximo Field | Notes |
|-------------------|-------------|-------|
| work_order_id | WONUM | Max 20 chars; Maximo may auto-generate |
| title | DESCRIPTION | Max 100 chars |
| status | STATUS | Map: open→WAPPR, in_progress→INPRG, completed→COMP, cancelled→CAN |
| priority | WOPRIORITY | Map: critical→1, high→2, medium→3, low→4 |
| asset_name | — | Use asset_id instead |
| asset_id | ASSETNUM | Must exist in Maximo asset registry |
| location | LOCATION | Maximo location hierarchy code |
| site | SITEID | Must match Maximo site configuration |
| assigned_to | LEAD | Person record in Maximo |
| assigned_team | CREWID | Crew/craft record |
| work_type | WORKTYPE | CM, PM, EM, etc. |
| category | CLASSSTRUCTUREID | Classification structure ID |
| due_date | TARGSTARTDATE | Target start date |
| created_date | REPORTDATE | Date reported |
| completed_date | ACTFINISH | Actual finish date |
| completed_by | — | Captured in labor transactions |
| reported_by | REPORTEDBY | Person record |
| channel | — | Custom field (FACTORYLM_CHANNEL) |
| estimated_hours | ESTDUR | Duration in hours |
| cost | ESTMATCOST | Estimated material cost |
| completion_notes | DESCRIPTION_LONGDESCRIPTION | Long description field |
| failure_code | FAILURECODE | Must exist in Maximo failure hierarchy |
| description | DESCRIPTION_LONGDESCRIPTION | Appended to long description |
| cmms_system | — | Not imported |
| cmms_external_id | — | Set after import (WONUM) |

### 2. Fiix (formerly eMaint CMMS)

Import method: CSV bulk import. **Requires integer IDs for status and priority.**

| FactoryLM Column | Fiix Field | Notes |
|-------------------|-----------|-------|
| work_order_id | strCode | Work order code |
| title | strDescription | Short description |
| status | intWorkOrderStatusID | Map: open→2, in_progress→3, completed→4, cancelled→5 |
| priority | intPriorityID | Map: critical→1, high→2, medium→3, low→4 |
| asset_name | — | Use asset_id |
| asset_id | strAssetIds | Pipe-delimited if multiple |
| location | strSiteIds | Site ID (integer, lookup required) |
| site | strSiteIds | Combined with location |
| assigned_to | intAssignedToUserID | Integer user ID (lookup required) |
| assigned_team | — | Assigned via user groups |
| work_type | intWorkOrderTypeID | Map: Corrective→1, Preventive→2 |
| category | intCategoryID | Integer category ID |
| due_date | dtmDateRequiredBy | Required-by date |
| created_date | dtmDateCreated | Auto-set by Fiix |
| completed_date | dtmDateCompleted | Completion timestamp |
| completed_by | intCompletedByUserID | Integer user ID |
| reported_by | — | Custom field |
| channel | — | Custom field |
| estimated_hours | intEstimatedHours | Integer only |
| cost | dblEstimatedCost | Double precision |
| completion_notes | strCompletionNotes | Free text |
| failure_code | strFailureCode | Custom field mapping |
| description | strDescription | Combined with title |
| cmms_system | — | Not imported |
| cmms_external_id | intWorkOrderID | Set after import |

### 3. SAP PM (Plant Maintenance) — OUTLIER

Import method: **XML via LTMC (Legacy Transfer Migration Cockpit)** or LSMW. Cannot use CSV directly.

| FactoryLM Column | SAP PM Field | Notes |
|-------------------|-------------|-------|
| work_order_id | AUFNR | Order number (12 digits, zero-padded) |
| title | KTEXT | Short text (40 chars max) |
| status | — | System status, set via BAPI |
| priority | PRIOK | Priority key: 1, 2, 3, 4 |
| asset_name | — | Use asset_id |
| asset_id | EQUNR | Equipment number (18 digits) |
| location | TPLNR | Functional location |
| site | WERKS | Plant code (4 chars) |
| assigned_to | PERNR | Personnel number |
| assigned_team | ARBPL | Work center |
| work_type | AUART | Order type: PM01, PM02, PM03 |
| category | — | Set via classification |
| due_date | GSTRP | Basic start date |
| created_date | ERDAT | Created date (auto) |
| completed_date | GETRI | Technical completion date |
| completed_by | — | Captured in confirmations |
| reported_by | ERNAM | Created by (user ID) |
| channel | — | Custom field (Z-field) |
| estimated_hours | ARBEI | Work (duration in hours) |
| cost | — | Calculated from operations |
| completion_notes | LTXA1 | Operation long text |
| failure_code | FECOD | Catalog code |
| description | LTXA1 | Operation long text |
| cmms_system | — | Not imported |
| cmms_external_id | AUFNR | Set after creation |

**Adapter required**: A future `sap_xml_adapter.py` will convert CSV to LTMC-compatible XML.

### 4. eMaint (standalone, separate from Fiix)

Import method: CSV upload via Admin > Import Data.

| FactoryLM Column | eMaint Field | Notes |
|-------------------|-------------|-------|
| work_order_id | Work Order Number | String |
| title | Description | Short description |
| status | WO Status | Open, In Progress, Completed, Closed |
| priority | Priority | Critical, High, Medium, Low |
| asset_name | Asset Name | Free text |
| asset_id | Asset ID | Must exist in eMaint |
| location | Location | Location hierarchy |
| site | Site | Facility name |
| assigned_to | Assigned To | User name |
| assigned_team | Trade | Maintenance trade |
| work_type | Work Order Type | Corrective, Preventive |
| category | Category | User-defined |
| due_date | Due Date | MM/DD/YYYY format |
| created_date | Date Created | Auto-set |
| completed_date | Date Completed | MM/DD/YYYY |
| completed_by | Completed By | User name |
| reported_by | Reported By | Free text |
| channel | — | Custom field |
| estimated_hours | Estimated Hours | Decimal |
| cost | Estimated Cost | Currency |
| completion_notes | Completion Notes | Free text |
| failure_code | Failure Code | User-defined codes |
| description | Extended Description | Long text |
| cmms_system | — | Not imported |
| cmms_external_id | — | Set after import |

### 5. Limble CMMS

Import method: CSV upload via Settings > Import.

| FactoryLM Column | Limble Field | Notes |
|-------------------|-------------|-------|
| work_order_id | — | Limble auto-generates IDs |
| title | Task Name | Primary identifier |
| status | Status | Open, In Progress, Complete |
| priority | Priority Level | 1=Critical, 2=High, 3=Medium, 4=Low |
| asset_name | Asset | Asset name or ID |
| asset_id | Asset ID | Must exist in Limble |
| location | Location | Location name |
| site | — | Combined with location |
| assigned_to | Assigned User | Email or username |
| assigned_team | Assigned Team | Team name |
| work_type | Type | Reactive, Preventive, Predictive |
| category | Category | User-defined |
| due_date | Due Date | YYYY-MM-DD |
| created_date | — | Auto-set by Limble |
| completed_date | Completed Date | YYYY-MM-DD |
| completed_by | Completed By | Username |
| reported_by | — | Custom field |
| channel | — | Custom field |
| estimated_hours | Estimated Time | **Minutes** (multiply hours × 60) |
| cost | Estimated Cost | Currency |
| completion_notes | Notes | Free text |
| failure_code | — | Custom field |
| description | Description | Long text |
| cmms_system | — | Not imported |
| cmms_external_id | — | Set after import |

**Note**: Limble expects `estimated_hours` in **minutes**. Multiply the FactoryLM value by 60 before import.

### 6. UpKeep

Import method: CSV upload or REST API (`POST /work-orders`).

| FactoryLM Column | UpKeep Field | Notes |
|-------------------|-------------|-------|
| work_order_id | — | UpKeep auto-generates IDs |
| title | title | **Only required field** |
| status | status | 0=Open, 1=In Progress, 2=On Hold, 3=Closed |
| priority | priority | 0=None, 1=Low, 2=Medium, 3=High |
| asset_name | — | Use asset system ID |
| asset_id | asset | System-generated asset ID (lookup required) |
| location | location | System-generated location ID (lookup required) |
| site | — | Part of location hierarchy |
| assigned_to | assignedToUser | System-generated user ID (lookup required) |
| assigned_team | team | System-generated team ID |
| work_type | category | Category name |
| category | category | Combined with work_type |
| due_date | dueDate | ISO 8601 |
| created_date | createdAt | Auto-set |
| completed_date | completedDate | ISO 8601 |
| completed_by | completedByUser | System user ID |
| reported_by | requester | System user ID |
| channel | — | Custom field |
| estimated_hours | estimatedHours | Decimal |
| cost | — | Calculated from parts/labor |
| completion_notes | description | Appended to description |
| failure_code | — | Custom field |
| description | description | Main description field |
| cmms_system | — | Not imported |
| cmms_external_id | id | Set after creation |

**Note**: UpKeep uses system-generated integer IDs for assets, locations, and users. A lookup step is required before import.

---

## Outlier Adapter Notes

### SAP PM XML Adapter (Future)

SAP Plant Maintenance cannot import CSV directly. A converter is needed:

```
work-order.csv → sap_xml_adapter.py → SAP LTMC XML
```

This adapter will:
1. Read the CSV row
2. Map columns to SAP PM fields (AUFNR, KTEXT, PRIOK, etc.)
3. Generate LTMC-compatible XML
4. Output a `.xml` file ready for upload

**Status**: Planned for Phase D / future sprint.

### Fracttal API (Future)

Fracttal CMMS uses a REST API exclusively — no CSV import. A future adapter will:
1. Read the CSV row
2. POST to `https://api.fracttal.com/api/work_orders/`
3. Map response ID back to `cmms_external_id`

**Status**: Not yet started. Lower priority than the 6 core systems.

---

## One-Click Integration Narrative

> **"Your factory already has a CMMS. FactoryLM doesn't replace it — it feeds it."**
>
> When a technician texts their factory from Telegram, FactoryLM diagnoses the issue and generates a work order as a GitHub Gist. That Gist contains a CSV that your CMMS can import in one click.
>
> No middleware. No integration platform. No monthly SaaS fee for a connector.
>
> Just download the CSV from the Gist and upload it to Maximo, Fiix, eMaint, Limble, or UpKeep. The work order appears in your CMMS with the right fields, the right priority, and photos attached.
>
> SAP shops get an XML adapter. Everyone else gets CSV. Done.
