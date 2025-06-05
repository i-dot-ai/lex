"""Integration tests for caselaw package."""

from lex.caselaw.models import Caselaw, CaselawSection, Court, CourtDivision
from lex.caselaw.parser import CaselawAndCaselawSectionsParser, CaselawParser, CaselawSectionParser
from lex.caselaw.scraper import CaselawScraper
from lex.core.utils import load_xml_file_to_soup


def test_caselaw_integration():
    """Test the full caselaw scraping and parsing pipeline."""
    # Initialize components
    scraper = CaselawScraper()
    parser = CaselawParser()
    section_parser = CaselawSectionParser()

    # Scrape and parse content
    caselaw = []
    caselaw_sections = []
    for caselaw_soup in scraper.load_content(years=[2024], limit=10):
        caselaw.append(parser.parse_content(caselaw_soup))
        caselaw_sections.extend(section_parser.parse_content(caselaw_soup))

    # Assertions
    assert len(caselaw) > 0, "Should have parsed at least one caselaw"
    assert len(caselaw_sections) > 0, "Should have parsed at least one caselaw section"

    # Check that each caselaw has basic required attributes
    for case in caselaw:
        assert case is not None
        assert isinstance(case, Caselaw)
        assert hasattr(case, "year")
        # assert case.year == 2024 # TODO: currently Caselaw doesn't filter by year

    # Check that each section has basic required attributes
    for section in caselaw_sections:
        assert section is not None
        assert isinstance(section, CaselawSection)
        assert hasattr(section, "text")


def test_caselaw_section_parser_nested_levels():
    """Test the CaselawSectionParser with a case containing nested levels structure."""
    # Initialize parser
    section_parser = CaselawSectionParser()
    caselaw_and_sections_parser = CaselawAndCaselawSectionsParser()

    # Load test data
    test_file = "tests/test_data/ewhc_admin_2017_3409.xml"
    soup = load_xml_file_to_soup(test_file)

    # Parse content

    # Assert that the caselaw section type is nested levels
    assert caselaw_and_sections_parser._get_caselaw_section_type(soup) == "nested_levels"

    # Parse content
    sections = section_parser.parse_content(soup)

    # Basic assertions about the result
    assert len(sections) > 0, "Should have parsed at least one section"

    # Test the metadata of the sections
    assert sections[0].caselaw_id == "https://caselaw.nationalarchives.gov.uk/ewhc/admin/2017/3409"
    assert sections[1].court == Court.EWHC
    assert sections[2].division == CourtDivision.ADMIN
    assert sections[3].year == 2017
    assert sections[4].number == 3409
    assert sections[5].cite_as == "[2017] EWHC 3409 (Admin)"

    # Test the id of a few candidates
    assert sections[4].id == "https://caselaw.nationalarchives.gov.uk/ewhc/admin/2017/3409-5"
    assert sections[19].id == "https://caselaw.nationalarchives.gov.uk/ewhc/admin/2017/3409-20"
    assert sections[80].id == "https://caselaw.nationalarchives.gov.uk/ewhc/admin/2017/3409-81"

    # Test the route structure for different sections
    assert all(section.route == ["Introduction"] for section in sections[0:4])
    assert all(section.route == ["Factual Background"] for section in sections[4:19])
    assert all(section.route == ["Ground 3"] for section in sections[90:97])

    # Test specific section content
    assert (
        sections[22].text
        == "22.Save in exceptional circumstances, PINS will only accept claims made in writing within six months of the date of the relevant error, or of any subsequent “appeal decision” related to that error."
    )
    assert (
        sections[80].text
        == "71.At paragraph 43 Lord Dyson MR stated that the well-established distinction between goodwill and future income is fundamental to the Strasbourg jurisprudence and continued: -“The important distinction is between the present day value of future income (which is not treated by the European court as part of goodwill and a possession) and the present day value of a business which reflects the capacity to earn profits in the future (which may be part of goodwill and a possession).  The capacity to earn profits in the future is derived from the reputation that the business enjoys as a result of its past efforts.”The Court of Appeal then decided that contracts which had already been concluded might be referable to “past efforts” and hence the goodwill of the business, but contracts yet to be concluded could not (paragraphs 48-49)."
    )


def test_caselaw_section_parser_default():
    """Test the CaselawSectionParser with a case containing nested levels structure."""
    # Initialize parser
    section_parser = CaselawSectionParser()
    caselaw_and_sections_parser = CaselawAndCaselawSectionsParser()

    # Load test data
    test_file = "tests/test_data/ewhc_ch_2017_3397.xml"
    soup = load_xml_file_to_soup(test_file)

    # Parse content

    # Assert that the caselaw section type is nested levels
    assert caselaw_and_sections_parser._get_caselaw_section_type(soup) == "default"

    # Parse content
    sections = section_parser.parse_content(soup)

    # Basic assertions about the result
    assert len(sections) > 0, "Should have parsed at least one section"

    # Test the metadata of the sections
    assert caselaw_and_sections_parser._get_caselaw_section_type(soup) == "default"

    assert sections[0].caselaw_id == "https://caselaw.nationalarchives.gov.uk/ewhc/ch/2017/3397"
    assert sections[1].court == Court.EWHC
    assert sections[2].division == CourtDivision.CH
    assert sections[3].year == 2017
    assert sections[4].number == 3397
    assert sections[5].cite_as == "[2017] EWHC 3397 (Ch)"

    # Test the id of a few candidates
    assert sections[4].id == "https://caselaw.nationalarchives.gov.uk/ewhc/ch/2017/3397-5"
    assert sections[19].id == "https://caselaw.nationalarchives.gov.uk/ewhc/ch/2017/3397-20"
    assert sections[80].id == "https://caselaw.nationalarchives.gov.uk/ewhc/ch/2017/3397-81"

    assert all(section.route == [] for section in sections)

    assert (
        sections[12].text
        == "12.\nMr Holyoake was a student at Reading University in the early 1990s where he met Mr Nicholas Candy.  He then set up a business called Bloomsbury International Ltd which was involved in the distribution and manufacture of food and seafood products.  This grew into a significant group of companies, known as British Seafood, which collapsed in early 2010, at least four of the companies, including Bloomsbury International Ltd itself, then one of the group’s principal trading companies, being put into administration on 19 February 2010 by Morgan J.  Mr Holyoake was then Chief Executive Officer or CEO of the four companies, as well as the majority owner of the business, holding over 50% of the ultimate holding company, British Seafood Group Holdings Ltd, and about 50% of a related holding company, British Seafood Distribution Group Holdings Ltd."
    )
    assert (
        sections[24].text
        == "24.\nThree other points by way of background can conveniently be noted here.  First, Mr \nHolyoake’s main business interest in 2011 was another seafood business.  This was Iceland Seafood International ehf (“ISI”), an Icelandic company.  Mr Holyoake was in the process of acquiring a substantial shareholding in it, using Oakvest Holdings sarl, a Luxembourg company wholly owned by him, which held a 55% interest in International Seafood Holdings sarl (“ISH”), another Luxembourg company, which had agreed to acquire the shares in ISI.  At the time of his acquiring GGH however, these shares had not been fully paid for."
    )

    assert len(sections) == 527


def test_caselaw_section_parser_quote_levels():
    """Test the CaselawSectionParser with a case containing quote levels structure."""
    # Initialize parser
    section_parser = CaselawSectionParser()
    caselaw_and_sections_parser = CaselawAndCaselawSectionsParser()

    # Load test data
    test_file = "tests/test_data/ewhc_admin_2017_3364.xml"
    soup = load_xml_file_to_soup(test_file)

    sections = section_parser.parse_content(soup)

    assert caselaw_and_sections_parser._get_caselaw_section_type(soup) == "quote_levels"

    assert sections[0].caselaw_id == "https://caselaw.nationalarchives.gov.uk/ewhc/admin/2017/3364"
    assert sections[1].court == Court.EWHC
    assert sections[2].division == CourtDivision.ADMIN
    assert sections[3].year == 2017
    assert sections[4].number == 3364
    assert sections[5].cite_as == "[2017] EWHC 3364 (Admin)"

    assert all(section.route == ["The Factual Background"] for section in sections[2:17])
    assert all(
        section.route == ["The parties’ submissions and discussion"] for section in sections[59:75]
    )
    assert all(section.route == ["Issue 4: facilitated exit"] for section in sections[91:102])

    assert sections[10].id == "https://caselaw.nationalarchives.gov.uk/ewhc/admin/2017/3364-11"
    assert sections[60].id == "https://caselaw.nationalarchives.gov.uk/ewhc/admin/2017/3364-61"

    assert (
        sections[10].text
        == "11.In addition he was made the subject of a Serious Crime Prevention Order (“SCPO”).  By the SCPO Mr Xu was required to deliver up all copies of the company’s intellectual property within his possession or control and disclose all third parties to whom he had allowed possession of or access to the confidential information and the location of any copies.  He was prevented from using the strategies anywhere in the world.  Confiscation proceedings were also commenced."
    )
    assert (
        sections[60].text
        == "61.I reject this submission.  I accept that in the response of 15 September 2017 the SSHD set out her reasons for her decision which was made on 11 September 2017.  The A&O representations that the Claimants A1P1 and Article 6 rights would be breached by Mr Xu’s deportation were not considered by the caseworkers, but by other officials.  Mr Tam explained that there were two strands to the decision making process: first, the conventional approach reflected in the internal documents of 11 September 2017 which involved consideration of whether Mr Xu was suggesting that he should not be deported; and second, that part of the decision making process which involved consideration of the Claimants’ representations.  It was after both strands of the decision making process had been completed that the deportation order was signed.  The letter and response sent by GLD on 15 September 2017 sets out the reasons of the decision makers.  Mr Tam acknowledged that the documentation is not the clearest as to what happened, but I am satisfied that the response of 15 September 2017 does record the SSHD’s reasons for her decision."
    )

    assert len(sections) == 106


def test_caselaw_section_parser_flat_paragraphs():
    """Test the CaselawSectionParser with a case containing flat paragraphs structure."""
    # Initialize parser
    section_parser = CaselawSectionParser()
    caselaw_and_sections_parser = CaselawAndCaselawSectionsParser()

    # Load test data
    test_file = "tests/test_data/ewhc_ch_2017_3414.xml"
    soup = load_xml_file_to_soup(test_file)

    assert caselaw_and_sections_parser._get_caselaw_section_type(soup) == "flat_paragraphs"

    sections = section_parser.parse_content(soup)

    assert sections[0].caselaw_id == "https://caselaw.nationalarchives.gov.uk/ewhc/ch/2017/3414"
    assert sections[1].court == Court.EWHC
    assert sections[2].division == CourtDivision.CH
    assert sections[3].year == 2017
    assert sections[4].number == 3414
    assert sections[5].cite_as == "[2017] EWHC 3414 (Ch)"

    assert all(section.route == [] for section in sections)

    assert sections[8].id == "https://caselaw.nationalarchives.gov.uk/ewhc/ch/2017/3414-9"
    assert sections[12].id == "https://caselaw.nationalarchives.gov.uk/ewhc/ch/2017/3414-13"

    assert (
        sections[8].text
        == "9.Secondly, the conclusion I reached at [36] (namely that streaming is a different technical means to cable or satellite broadcasts which requires a separate authorisation from the rightholder) is supported by the subsequent decision of the CJEU in Case C-265/16 VCAST Ltd v RTI SpA [EU:C:2017:913] at [48]-[50]."
    )
    assert (
        sections[12].text
        == "13.Thirdly, the order sought by UEFA contains the same three criteria for selection of Target Servers as the orders in FAPL v BT (see FAPL v BT I at [21]), but it also includes a fourth criterion which provides an additional safeguard against overblocking."
    )

    assert len(sections) == 15


def test_caselaw_section_parser_levels_and_paragraphs():
    """Test the CaselawSectionParser with a case containing levels and paragraphs structure."""
    # Initialize parser
    section_parser = CaselawSectionParser()
    caselaw_and_sections_parser = CaselawAndCaselawSectionsParser()

    # Load test data
    test_file = "tests/test_data/ewfc_2017_83.xml"
    soup = load_xml_file_to_soup(test_file)

    assert caselaw_and_sections_parser._get_caselaw_section_type(soup) == "levels_and_paragraphs"

    sections = section_parser.parse_content(soup)

    assert sections[0].caselaw_id == "https://caselaw.nationalarchives.gov.uk/ewfc/2017/83"
    assert sections[1].court == Court.EWFC
    assert sections[2].division is None
    assert sections[3].year == 2017
    assert sections[4].number == 83
    assert sections[5].cite_as == "[2017] EWFC 83"

    assert all(section.route == ["Background"] for section in sections[1:5])

    assert (
        sections[0].text
        == "1.By the order dated 27 June 2017 I vacated a 2 day hearing that had been listed on 29 June to determine an application for a declaration of parental responsibility relating to a young child, X. In that order I reserved costs. Y now seeks an order that his costs relating to that application are paid by Z. Z resists that application. I have had the benefit of detailed written argument on costs by both parties and it is agreed I should determine the issue on consideration of the papers."
    )
    assert (
        sections[3].text
        == "4.On 9 June Z’s solicitor informed the parties that he did not wish to pursue his application for a declaration and proposed that the hearing on 29 June should be vacated. Y’s solicitors responded seeking clarification as to whether or not Z accepted he did not have parental responsibility for X, and he was requested to confirm his position by 16 June. There then followed correspondence between the parties’ solicitors, and it was not until 21 June that Z agreed to a recital that he accepted he did not have parental responsibility. A consent order was submitted to the court on 27 June, which was approved and provided for the costs to be reserved."
    )

    assert len(sections) == 9
