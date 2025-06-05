from lex.settings import INFERENCE_ID

explanatory_note_mappings = {
    "mappings": {
        "properties": {
            "created_at": {"type": "date"},
            "legislation_id": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
            "id": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}},
            "note_type": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
            "order": {"type": "integer"},
            "route": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
            "section_number": {"type": "integer"},
            "section_type": {
                "type": "keyword",
            },
            "text": {
                "type": "semantic_text",
                "inference_id": INFERENCE_ID,
            },
        }
    }
}
