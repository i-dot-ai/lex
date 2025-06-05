from lex.settings import INFERENCE_ID

legislation_mappings = {
    "mappings": {
        "properties": {
            "category": {
                "type": "keyword",
            },
            "created_at": {"type": "date"},
            "description": {
                "type": "text",
            },
            "enactment_date": {"type": "date"},
            "extent": {
                "type": "keyword",
            },
            "id": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}},
            "modified_date": {"type": "date"},
            "number": {
                "type": "integer",
            },
            "number_of_provisions": {"type": "integer"},
            "publisher": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
            "status": {
                "type": "keyword",
            },
            "title": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
            "type": {
                "type": "keyword",
            },
            "uri": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
            "valid_date": {"type": "date"},
            "year": {"type": "integer"},
        }
    }
}

legislation_section_mappings = {
    "mappings": {
        "properties": {
            "created_at": {"type": "date"},
            "extent": {
                "type": "keyword",
            },
            "id": {"type": "text", "fields": {"keyword": {"type": "keyword", "ignore_above": 256}}},
            "legislation_number": {"type": "integer"},
            "legislation_id": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
            "legislation_type": {
                "type": "keyword",
            },
            "legislation_year": {"type": "integer"},
            "number": {
                "type": "integer",
            },
            "provision_type": {
                "type": "keyword",
            },
            "text": {
                "type": "semantic_text",
                "inference_id": INFERENCE_ID,
            },
            "title": {
                "type": "text",
            },
            "uri": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword", "ignore_above": 256}},
            },
        }
    }
}
