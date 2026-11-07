import ag_tokens_inspector


def test_version_is_string():
    assert isinstance(ag_tokens_inspector.__version__, str)


def test_app_name_is_string():
    assert ag_tokens_inspector.__app_name__ == "ag-tokens-inspector"
