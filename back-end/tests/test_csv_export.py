"""Characterization of generate_csv_data — the BDC export CSV shape.

This is a pure function (no DB), so it's a real unit test of production code."""

from types import SimpleNamespace

from controllers.database_controller.kml_ops import generate_csv_data

EXPECTED_COLUMNS = [
    "provider_id",
    "brand_name",
    "location_id",
    "technology",
    "max_advertised_download_speed",
    "max_advertised_upload_speed",
    "low_latency",
    "business_residential_code",
]


def _row(location_id, tech=50, dl=100, ul=20, latency=1, category="R"):
    return SimpleNamespace(
        location_id=location_id,
        techType=tech,
        maxDownloadSpeed=dl,
        maxUploadSpeed=ul,
        latency=latency,
        category=category,
    )


def test_columns_and_order():
    df = generate_csv_data([_row(1), _row(2)], provider_id=330054, brand_name="Acme")
    assert list(df.columns) == EXPECTED_COLUMNS
    assert len(df) == 2


def test_dedup_on_location_and_technology():
    rows = [_row(1, tech=50), _row(1, tech=50), _row(1, tech=70)]
    df = generate_csv_data(rows, provider_id=330054, brand_name="Acme")
    # (1,50) collapses to one; (1,70) stays — so 2 rows.
    assert len(df) == 2
    assert set(zip(df.location_id, df.technology)) == {(1, 50), (1, 70)}


def test_provider_and_brand_are_filled():
    df = generate_csv_data([_row(1), _row(2)], provider_id=330054, brand_name="Acme")
    assert (df.provider_id == 330054).all()
    assert (df.brand_name == "Acme").all()
