from lex.settings import INFERENCE_ID

caselaw_mappings = {
    "mappings": {
        "properties": {
            "cite_as": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
            "court": {
                "type": "keyword",
            },
            "created_at": {"type": "date"},
            "date": {"type": "date"},
            "date_of": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
            "division": {
                "type": "keyword",
            },
            "caselaw_id": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
            "header": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
            "name": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
            "number": {"type": "integer"},
            "text": {
                "type": "semantic_text",
                "inference_id": INFERENCE_ID,
            },
            "caselaw_references": {"type": "keyword", "ignore_above": 256},
            "legislation_references": {"type": "keyword", "ignore_above": 256},
            "year": {"type": "integer"},
        }
    }
}

caselaw_section_mappings = {
    "mappings": {
        "properties": {
            "caselaw_id": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
            "court": {
                "type": "keyword",
            },
            "division": {
                "type": "keyword",
            },
            "year": {"type": "integer"},
            "number": {"type": "integer"},
            "cite_as": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
            "created_at": {"type": "date"},
            "id": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}},
            "order": {"type": "integer"},
            "route": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
            "text": {
                "type": "semantic_text",
                "inference_id": INFERENCE_ID,
            },
        }
    }
}
