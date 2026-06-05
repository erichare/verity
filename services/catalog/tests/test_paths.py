from verity_catalog.ingest import parse_lea


def test_parse_underscore_style():
    assert parse_lea("Hamby252_Barrel1_Bullet2_Land3.x3p") == (1, 2, 3)


def test_parse_path_style():
    assert parse_lea("Barrel 10/Bullet 1/Land 6.x3p") == (10, 1, 6)


def test_parse_no_match():
    assert parse_lea("random_scan.x3p") is None
