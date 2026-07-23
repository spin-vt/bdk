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


def test_default_reports_every_technology_claim_outside_fixed_wireless():
    """The BDC accepts multiple technology claims per location as long as at
    most one is fixed wireless; by default a location under several coverages
    files a row per (non-conflicting) technology."""
    rows = [_row(1, tech=50), _row(1, tech=10), _row(1, tech=71)]
    df = generate_csv_data(rows, provider_id=330054, brand_name="Acme")
    assert set(zip(df.location_id, df.technology)) == {(1, 10), (1, 50), (1, 71)}


def test_default_collapses_fixed_wireless_to_the_fastest_claim():
    """The BDC rejects a filing that claims more than one fixed-wireless
    technology (70/71/72) at a location, so by default only the fastest
    fixed-wireless claim survives; claims under other technologies still file
    alongside it."""
    rows = [
        _row(1, tech=70, dl=25, ul=3),
        _row(1, tech=71, dl=100, ul=20),  # fastest fixed wireless -> survives
        _row(1, tech=72, dl=50, ul=10),
        _row(1, tech=50, dl=1000, ul=1000),  # not fixed wireless -> kept too
        _row(2, tech=70, dl=25, ul=3),  # sole fixed-wireless claim -> untouched
    ]
    df = generate_csv_data(rows, provider_id=330054, brand_name="Acme")
    assert set(zip(df.location_id, df.technology)) == {(1, 50), (1, 71), (2, 70)}
    kept = df[(df.location_id == 1) & (df.technology == 71)].iloc[0]
    assert kept.max_advertised_download_speed == 100  # the winner's own values
    assert kept.max_advertised_upload_speed == 20


def test_fixed_wireless_collapse_uses_the_max_service_tiebreaks():
    """The fixed-wireless collapse ranks claims exactly like max_service_only:
    download desc, then upload desc, then low-latency first, then the lowest
    technology code."""
    rows = [
        _row(2, tech=70, dl=100, ul=50),
        _row(2, tech=71, dl=100, ul=75),  # same download, faster upload -> wins
        _row(3, tech=72, dl=100, ul=20, latency=1),  # low latency wins the tie
        _row(3, tech=71, dl=100, ul=20, latency=0),
        _row(4, tech=71, dl=100, ul=20),
        _row(4, tech=70, dl=100, ul=20),  # full tie -> lowest tech code
    ]
    df = generate_csv_data(rows, provider_id=330054, brand_name="Acme")
    assert set(zip(df.location_id, df.technology)) == {(2, 71), (3, 72), (4, 70)}


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
