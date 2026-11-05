# Implementation Plan: Canva-Style Dynamic Multi-Field Certificate Editor

**Date:** 2026-11-05  
**Feature:** Canva-Style Drag-and-Drop Certificate Editor with Arbitrary Dynamic Fields  
**Target:** Render Free Tier (512MB RAM) & Firebase Free Tier safe

---

## 1. Problem & Context
Organizers currently only have a single position slider for the participant's name. They need:
1. Multiple custom fields on certificates (e.g. `Participant Name`, `Event Name`, `Issue Date`, `Certificate ID`, `College / Institute`, `Rank / Position`, `Department`, `Roll No`).
2. A Canva-like visual drag-and-drop editor directly on the certificate background, eliminating coordinate guesswork.
3. Automatic column mapping from uploaded Excel/CSV spreadsheets directly onto certificate templates.

### Free-Tier & System Constraints (Preventing Previous Clashes)
1. **Render 512MB RAM Limit:**
   - **Client-Side Live Preview:** All visual dragging, font changes, and positioning happen **100% in the browser** via React DOM/Canvas coordinates without sending network requests to Render while dragging. Render is only touched when explicitly saving or generating the final PDF.
   - **Zero Pillow Memory Leaks:** Backend PDF generation opens images, renders text with explicit anchors, saves to buffer, and immediately calls `img.close()` and `buffer.close()` within `try...finally` blocks.
2. **Firestore Free Quota Protection:**
   - Template configuration is stored directly inside the campaign document (`campaign.template.config.fields`), incurring **zero additional database reads** when fetching the campaign.
3. **Sequential Dispatch & Thread Safety:**
   - Sequential batch dispatch (`CONCURRENCY_LIMIT = 1`) and Gmail API thread locks remain untouched and fully preserved.
4. **Backwards Compatibility:**
   - Existing campaigns (e.g. `camp_d42cbf9e2dcc`) without `fields` will automatically fall back to legacy `name_x_percent` / `font_family` without any broken templates or database migrations.

---

## 2. Proposed Architecture & Files Touched

```
                    ┌────────────────────────────────────────────────────────┐
                    │               CanvaCertificateEditor                   │
                    │   - Visual drag-and-drop on template image             │
                    │   - Local 60fps React state (Zero Render RAM churn)    │
                    │   - Variable palette: {{name}}, {{college}}, etc.      │
                    └───────────────────────────┬────────────────────────────┘
                                                │ Saves config
                                                ▼
┌───────────────────────────┐      ┌───────────────────────────┐
│ backend/app/schemas/      │      │ backend/app/services/     │
│ template.py               │◄────►│ certificate_service.py    │
│  - CertificateField model │      │  - Multi-field PIL text   │
│  - TemplateConfig.fields  │      │  - Dynamic variables      │
└───────────────────────────┘      └─────────────┬─────────────┘
                                                 │
                                                 ▼
                                   ┌───────────────────────────┐
                                   │ batch_engine.py           │
                                   │  - Passes spreadsheet     │
                                   │    variables into PDF     │
                                   └───────────────────────────┘
```

### Files Created or Modified:
- `backend/app/schemas/template.py` (Add `CertificateField` schema & `fields` list on `TemplateConfig`)
- `backend/app/services/certificate_service.py` (Render all enabled dynamic fields using Pillow)
- `backend/app/api/endpoints/participants.py` (Capture all extra Excel spreadsheet columns into participant `variables`)
- `backend/app/services/batch_engine.py` (Inject participant `variables` into on-the-fly certificate PDF generation)
- `backend/tests/test_dynamic_certificate_fields.py` (Comprehensive unit & integration tests)
- `frontend/src/services/templates.ts` (TypeScript types for `CertificateField` and `TemplateConfig`)
- `frontend/src/components/certificates/CanvaCertificateEditor.tsx` (Canva-style visual editor component)
- `frontend/src/components/certificates/CertificateStudio.tsx` (Integrate CanvaCertificateEditor seamlessly)

---

## 3. Tasks Breakdown

### Task 1: Backend Data Schema for Multi-Field Templates
- **Files:** `backend/app/schemas/template.py`
- **Actions:**
  - Define `CertificateField` Pydantic model (`id`, `label`, `variable_key`, `x_percent`, `y_percent`, `font_family`, `font_size`, `font_color`, `text_align`, `is_enabled`).
  - Add `fields: Optional[List[CertificateField]] = None` to `TemplateConfig`.
  - Add helper `get_normalized_fields()` to automatically migrate legacy configs.

### Task 2: Backend Multi-Field Image & PDF Rendering
- **Files:** `backend/app/services/certificate_service.py`
- **Actions:**
  - Update `render_certificate_image` to iterate over all active fields from `config["fields"]`.
  - Resolve text values from `participant_variables` (mapping `{{name}}`, `{{college}}`, `{{date}}`, etc.).
  - Apply custom font, size, color, anchor for each field.
  - Wrap in strict memory cleanup (`img.close()`).

### Task 3: Spreadsheet Column Extraction to Participant Variables
- **Files:** `backend/app/api/endpoints/participants.py`
- **Actions:**
  - In `upload_participants`, capture all extra columns beyond `name` and `email` into `part_data["variables"]`.
  - Store available campaign custom column names in the campaign document for frontend variable discovery.

### Task 4: Batch Engine Integration
- **Files:** `backend/app/services/batch_engine.py`
- **Actions:**
  - When auto-generating certificate PDF on the fly, pass the full participant `variables` dict into `certificate_service.generate_pdf_bytes`.

### Task 5: Backend Automated Unit Tests
- **Files:** `backend/tests/test_dynamic_certificate_fields.py`
- **Actions:**
  - Test multi-field template serialization.
  - Test Pillow multi-field rendering with custom fonts and Excel columns.
  - Test backwards compatibility fallback with legacy configs.

### Task 6: Frontend Types & Canva-Style Visual Editor Component
- **Files:** `frontend/src/services/templates.ts`, `frontend/src/components/certificates/CanvaCertificateEditor.tsx`
- **Actions:**
  - Update TypeScript interfaces with `CertificateField`.
  - Build `CanvaCertificateEditor` with:
    - Interactive drag handles on the template image.
    - Canva-style top toolbar (Font, Size, Color, Alignment, Add Field).
    - Variable drawer / pill palette (Standard: Name, Date, Cert ID; Excel Columns: College, Rank, etc.).
    - Client-side coordinate recalculation (`x_percent`, `y_percent`).

### Task 7: Integrate into CertificateStudio & Full Verification
- **Files:** `frontend/src/components/certificates/CertificateStudio.tsx`
- **Actions:**
  - Embed `CanvaCertificateEditor` in place of the static slider controls.
  - Run `pytest backend/tests` to verify 100% test pass.
  - Run `npm run build --prefix frontend` to ensure zero TypeScript errors.
  - Commit and deploy.

