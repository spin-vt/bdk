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


def test_default_reports_every_technology_claim():
    """The BDC accepts multiple technology claims per location; by default a
    location under several coverages files a row per technology."""
    rows = [_row(1, tech=50), _row(1, tech=70), _row(1, tech=71)]
    df = generate_csv_data(rows, provider_id=330054, brand_name="Acme")
    assert set(zip(df.location_id, df.technology)) == {(1, 50), (1, 70), (1, 71)}


def test_max_service_only_picks_the_fastest_claim_per_location():
    """With max_service_only, a location files exactly ONE row — the fastest
    claim: download desc, then upload desc, then low-latency first, then the
    lowest technology code as a deterministic tiebreak. The surviving row
    keeps its own values."""
    rows = [
        _row(1, tech=50, dl=1000, ul=1000),
        _row(1, tech=70, dl=25, ul=3),  # slower -> dropped
        _row(2, tech=70, dl=100, ul=50),
        _row(2, tech=71, dl=100, ul=75),  # same download, faster upload -> wins
        _row(3, tech=70, dl=100, ul=20, latency=0),
        _row(3, tech=71, dl=100, ul=20, latency=1),  # low latency wins the tie
        _row(4, tech=71, dl=100, ul=20),
        _row(4, tech=70, dl=100, ul=20),  # full tie -> lowest tech code
    ]
    df = generate_csv_data(rows, provider_id=330054, brand_name="Acme", max_service_only=True)
    assert set(zip(df.location_id, df.technology)) == {(1, 50), (2, 71), (3, 71), (4, 70)}
    kept = df[df.location_id == 1].iloc[0]
    assert kept.max_advertised_download_speed == 1000  # the winner's own values
