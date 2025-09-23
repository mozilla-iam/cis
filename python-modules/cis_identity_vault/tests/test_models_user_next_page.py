from cis_identity_vault.models.user import last_evaluated_to_friendly, next_page_to_dynamodb


def test_identity():
    expected = [None, None, {"id": {"S": "deadbeef"}}, {"id": {"S": "feedbeef"}}, None, None]
    assert expected == next_page_to_dynamodb(last_evaluated_to_friendly(expected))


def test_identity_two():
    assert None == next_page_to_dynamodb(last_evaluated_to_friendly(None))
