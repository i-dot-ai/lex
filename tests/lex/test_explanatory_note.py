"""Integration tests for explanatory note package."""

from lex.explanatory_note.parser import ExplanatoryNoteParser
from lex.legislation.models import LegislationType
from lex.legislation.scraper import LegislationScraper


def test_explanatory_note_integration():
    """Test the full explanatory note scraping and parsing pipeline."""
    # Initialize components
    scraper = LegislationScraper()
    parser = ExplanatoryNoteParser()

    # Scrape and parse content
    explanatory_note = []
    for url, soup in scraper.load_content(years=[2024], types=[LegislationType.UKPGA], limit=10):
        for note in parser.parse_content(soup):
            explanatory_note.append(note)

    # Assertions
    assert len(explanatory_note) > 0, "Should have parsed at least one explanatory note"

    # Check that each explanatory note has basic required attributes
    for note in explanatory_note:
        assert note is not None
        # Add more specific assertions based on the ExplanatoryNote model structure
        # These would need to be updated based on the actual model implementation
        assert hasattr(note, "id")  # Assuming there's a content field
        assert hasattr(note, "legislation_id")  # Assuming there's a reference to the legislation


def test_explanatory_note_parsing():
    """Test the parsing of explanatory notes."""
    # Initialize components
    scraper = LegislationScraper()
    parser = ExplanatoryNoteParser()

    url_ukpga = "https://www.legislation.gov.uk/ukpga/2020/25/data.xml"

    soup = scraper.load_legislation_from_url(url_ukpga)

    res = list(parser.parse_content(soup))

    assert (
        res[0].text
        == "These Explanatory Notes relate to the Parliamentary Constituencies Act 2020 (c. 25) which received Royal Assent on 14 December 2020.\n\tThese Explanatory Notes have been prepared by the Cabinet Office in order to assist the reader in understanding the Act. They do not form part of the Act and have not been endorsed by Parliament.\n\tThese Explanatory Notes explain what each part of the Act will mean in practice; provide background information on the development of policy; and provide additional information on how the Act will affect existing legislation in this area.\n\tThese Explanatory Notes might best be read alongside the Act. They are not, and are not intended to be, a comprehensive description of the Act."
    )

    url_uksi = "https://www.legislation.gov.uk/uksi/2012/2914/made/data.xml"

    soup = scraper.load_legislation_from_url(url_uksi)

    res = list(parser.parse_content(soup))

    assert (
        res[0].text
        == "\nEXPLANATORY NOTE\n\n(This note is not part of the Regulations)\n\nThese Regulations contain rules for the calculation of the council tax base, which is an amount required by the 1992 Act to be used in the calculation of the council tax by billing authorities and major precepting authorities and in the calculation of the amount of a precept payable by each billing authority to a major precepting authority. They apply to the financial years beginning on or after 1st April 2013.\nRegulations 3 to 5 provide for the calculation of the amount of a billing authority’s council tax base for the purposes of the calculation of its council tax. Under the rules, the council tax base is, in essence, the number of dwellings in an area belonging to each valuation band, modified to take account of the proportion applying to dwellings in each band under section 5 of the 1992 Act, discounts under sections 11 and 11A, in certain cases increases due to the application of the empty homes premium under section 11B and in others reduced amounts payable under section 13 of the Act, as well as reductions under a council tax reductions scheme required by section 13A, and the proportion of the council tax for the year which the billing authority expects to be able to collect.\nRegulation 6 provides for the calculation of a billing authority’s council tax base for a part of its area for the purposes of the calculation of its council tax similarly to the way in which the council tax base is to be calculated for the whole of a billing authority’s area under regulations 3 to 5.\nRegulation 7 provides for the calculation of the council tax base of the area or part of the area of a billing authority for the purposes of the calculation of a major precepting authority’s council tax and the amount payable by a billing authority to a major precepting authority, based on the rules set out in regulations 3 to 6.\nRegulation 8 prescribes a period for the notification by a billing authority of the council tax base of its area or a part of its area to a major precepting authority. Regulations 9 and 10 make provision for how the council tax base is to be determined where a billing authority fails to notify its calculation to a major precepting authority within the period prescribed by regulation 8. Regulation 11 provides for the determination of council tax base for the purposes of a local precepting authority and regulation 12 makes certain consequential amendments to regulations.\nRegulation 13 and the Schedule revoke the Local Authorities (Calculation of Council Tax Base) (England) Regulations 1992 and subsequent amending instruments.\nA full impact assessment has not been produced for this instrument as no impact on the private or voluntary sectors is foreseen.\n"
    )
