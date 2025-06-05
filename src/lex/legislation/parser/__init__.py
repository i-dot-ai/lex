"""
The parsing logic for legislation is taken from the Incubator for AI (i.AI) lex-graph repository (https://github.com/i-dot-ai/lex-graph).

In the future, i.AI aims to remove the duplication of code between these repositories so that both lex-graph and the lex-api server can benefit from the same loading, scraping, and parsing logic.

This repository has been been inspired by that codebase, but has been modified to focus more on correct text extraction. The graph structure is not uploaded to Elasticsearch, while a custom text extraction parser is created.

If this is something that you are interested in, please get in touch with us.
"""

from .parser import LegislationParser, LegislationSectionParser

__all__ = ["LegislationParser", "LegislationSectionParser"]
