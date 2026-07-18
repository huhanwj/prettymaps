def test_pipeline_importable():
    import pipeline  # noqa: F401


def test_fixtures(campus_square, synthetic_relation):
    assert campus_square.area > 0
    assert synthetic_relation["elements"][0]["id"] == 7802779
