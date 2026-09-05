from analysis_utils import (
    detect_text_column,
    normalize_topics,
    parse_topics_column,
    strip_markdown_code_fence,
)


class TestStripMarkdownCodeFence:
    def test_json_fence_with_language_tag(self):
        assert strip_markdown_code_fence('```json\n{"a": 1}\n```') == '{"a": 1}'

    def test_plain_fence(self):
        assert strip_markdown_code_fence('```\n{"a": 1}\n```') == '{"a": 1}'

    def test_no_fence_passthrough(self):
        assert strip_markdown_code_fence('{"a": 1}') == '{"a": 1}'

    def test_strips_surrounding_whitespace(self):
        assert strip_markdown_code_fence('  {"a": 1}  ') == '{"a": 1}'


class TestNormalizeTopics:
    def test_valid_list_passthrough(self):
        assert normalize_topics(["price", "quality"]) == ["price", "quality"]

    def test_single_string_becomes_list(self):
        assert normalize_topics("price") == ["price"]

    def test_empty_list_defaults_to_unknown(self):
        assert normalize_topics([]) == ["unknown"]

    def test_none_defaults_to_unknown(self):
        assert normalize_topics(None) == ["unknown"]

    def test_filters_out_non_strings_and_single_chars(self):
        # "a" отфильтровывается (len <= 1), 5 отфильтровывается (не строка)
        assert normalize_topics(["a", 5, "quality"]) == ["quality"]

    def test_garbage_type_defaults_to_unknown(self):
        assert normalize_topics({"not": "a list"}) == ["unknown"]


class TestParseTopicsColumn:
    def test_none_returns_empty(self):
        assert parse_topics_column(None) == []

    def test_error_sentinel_returns_empty(self):
        assert parse_topics_column("error") == []

    def test_empty_json_array_returns_empty(self):
        assert parse_topics_column("[]") == []

    def test_valid_json_list(self):
        assert parse_topics_column('["price", "quality"]') == ["price", "quality"]

    def test_invalid_json_returns_empty_not_raises(self):
        assert parse_topics_column("not valid json{{{") == []

    def test_valid_json_but_not_a_list_returns_empty(self):
        assert parse_topics_column('{"a": 1}') == []

    def test_filters_single_char_entries(self):
        assert parse_topics_column('["a", "quality"]') == ["quality"]


class TestDetectTextColumn:
    def test_finds_first_matching_candidate(self):
        assert detect_text_column(["id", "review_text", "date"]) == "review_text"

    def test_prefers_earlier_candidate_order(self):
        # "text" стоит раньше "review_text" в списке кандидатов по умолчанию
        assert detect_text_column(["review_text", "text"]) == "text"

    def test_no_match_returns_none(self):
        assert detect_text_column(["id", "date", "score"]) is None

    def test_custom_candidates(self):
        assert detect_text_column(["body"], candidates=["body", "text"]) == "body"
