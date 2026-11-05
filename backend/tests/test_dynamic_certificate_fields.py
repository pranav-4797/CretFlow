"""
Unit tests for Canva-style dynamic multi-field certificate templating.
Tests TemplateConfig schema, pillow multi-field rendering, variable resolution, and Excel column extraction.
"""

import io
import pytest
from PIL import Image
from httpx import AsyncClient, ASGITransport
from fastapi import status

from main import app
from app.core.security import AuthenticatedUser, get_current_user
from app.schemas.template import CertificateField, TemplateConfig
from app.services.certificate_service import certificate_service
from app.services.firestore_service import firestore_service


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
def auth_user():
    user = AuthenticatedUser(uid="user_template_tester", email="tester@example.com")
    app.dependency_overrides[get_current_user] = lambda: user
    yield user
    app.dependency_overrides.pop(get_current_user, None)


def _create_sample_template_bytes() -> bytes:
    """Generate blank image bytes simulating an uploaded certificate template."""
    img = Image.new("RGB", (1200, 800), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_template_config_legacy_fallback():
    """Verify that a legacy single-name config automatically converts to effective fields."""
    legacy = TemplateConfig(
        font_family="Cinzel",
        font_size=52,
        font_color="#b45309",
        name_x_percent=55.0,
        name_y_percent=45.0,
        show_cert_id=True,
        show_date=True,
    )
    fields = legacy.get_effective_fields()
    assert len(fields) == 3
    assert fields[0].variable_key == "name"
    assert fields[0].font_family == "Cinzel"
    assert fields[0].x_percent == 55.0
    assert fields[1].variable_key == "certificate_id"
    assert fields[2].variable_key == "date"


def test_template_config_modern_fields():
    """Verify modern Canva-style multi-field layout serialization."""
    modern = TemplateConfig(
        fields=[
            CertificateField(
                id="f_name",
                label="Student Name",
                variable_key="name",
                x_percent=50.0,
                y_percent=40.0,
                font_family="GreatVibes",
                font_size=64,
                font_color="#0f172a",
                text_align="center",
                is_enabled=True,
            ),
            CertificateField(
                id="f_college",
                label="College / Institute",
                variable_key="college",
                x_percent=50.0,
                y_percent=52.0,
                font_family="Montserrat",
                font_size=32,
                font_color="#475569",
                text_align="center",
                is_enabled=True,
            ),
            CertificateField(
                id="f_rank",
                label="Award / Rank",
                variable_key="rank",
                x_percent=50.0,
                y_percent=62.0,
                font_family="Cinzel",
                font_size=36,
                font_color="#b45309",
                text_align="center",
                is_enabled=True,
            ),
        ]
    )
    eff = modern.get_effective_fields()
    assert len(eff) == 3
    assert eff[0].variable_key == "name"
    assert eff[1].variable_key == "college"
    assert eff[2].variable_key == "rank"


def test_render_multi_field_image_and_pdf():
    """Verify Pillow draws all dynamic fields and produces a valid PDF."""
    tmpl_bytes = _create_sample_template_bytes()
    config = {
        "fields": [
            {
                "id": "f_name",
                "label": "Name",
                "variable_key": "name",
                "x_percent": 50.0,
                "y_percent": 40.0,
                "font_family": "PlayfairDisplay",
                "font_size": 48,
                "font_color": "#1e293b",
                "text_align": "center",
                "is_enabled": True,
            },
            {
                "id": "f_college",
                "label": "College",
                "variable_key": "college",
                "x_percent": 50.0,
                "y_percent": 50.0,
                "font_family": "Montserrat",
                "font_size": 28,
                "font_color": "#64748b",
                "text_align": "center",
                "is_enabled": True,
            },
            {
                "id": "f_rank",
                "label": "Rank",
                "variable_key": "rank",
                "x_percent": 50.0,
                "y_percent": 60.0,
                "font_family": "Cinzel",
                "font_size": 32,
                "font_color": "#b45309",
                "text_align": "center",
                "is_enabled": True,
            },
        ]
    }
    part_vars = {
        "college": "MIT Academy of Engineering",
        "rank": "1st Prize Winner",
    }

    # Render image
    rendered = certificate_service.render_certificate_image(
        template_bytes=tmpl_bytes,
        participant_name="Pooja Sharma",
        config=config,
        certificate_id="CERT-TEST-999",
        participant_variables=part_vars,
    )
    assert rendered.size == (1200, 800)
    rendered.close()

    # Generate PDF bytes
    pdf_bytes = certificate_service.generate_pdf_bytes(
        template_bytes=tmpl_bytes,
        participant_name="Pooja Sharma",
        config=config,
        certificate_id="CERT-TEST-999",
        participant_variables=part_vars,
    )
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF")


@pytest.mark.anyio
async def test_spreadsheet_custom_column_extraction(client: AsyncClient, auth_user: AuthenticatedUser):
    """Verify that spreadsheet columns like College and Rank are extracted into participant variables."""
    camp = firestore_service.create_campaign({
        "name": "Hackathon 2026",
        "user_id": auth_user.uid,
    })
    camp_id = camp["id"]

    csv_data = (
        "Name,Email,College,Rank,Score\n"
        "Alex Rivera,alex@example.com,Stanford University,1st Place,98.5\n"
        "Sam Chen,sam@example.com,MIT,2nd Place,94.0\n"
    ).encode("utf-8")

    res_upload = await client.post(
        f"/api/participants/{camp_id}/upload",
        files={"file": ("hackathon.csv", io.BytesIO(csv_data), "text/csv")},
    )
    assert res_upload.status_code == status.HTTP_200_OK

    # Verify participant has variables populated
    res_list = await client.get(f"/api/participants/{camp_id}")
    assert res_list.status_code == status.HTTP_200_OK
    parts = res_list.json()
    assert len(parts) == 2
    alex = next(p for p in parts if p["email"] == "alex@example.com")
    assert alex["variables"]["college"] == "Stanford University"
    assert alex["variables"]["rank"] == "1st Place"
    assert alex["variables"]["score"] == "98.5"

    # Verify campaign tracked available variables for Canva palette
    camp_doc = firestore_service.get_campaign(camp_id)
    assert "college" in camp_doc.get("available_variables", [])
    assert "rank" in camp_doc.get("available_variables", [])


def test_small_font_size_validation_and_rendering():
    """Verify that small font sizes (e.g. 4pt, 6pt, 8pt) are supported by schema and Pillow."""
    field = CertificateField(
        id="f_tiny",
        label="Small Note",
        variable_key="name",
        font_size=4,
    )
    assert field.font_size == 4

    config = TemplateConfig(
        font_size=6,
        fields=[field],
    )
    assert config.font_size == 6

    tmpl_bytes = _create_sample_template_bytes()
    img = certificate_service.render_certificate_image(
        template_bytes=tmpl_bytes,
        participant_name="Tiny Text",
        config=config.model_dump(),
    )
    assert img.size == (1200, 800)
    img.close()


