"""Integration tests for legislation package."""

import pytest
from bs4 import BeautifulSoup

from lex.core.http import HttpClient
from lex.core.utils import load_xml_file_to_soup
from lex.legislation.loader import LegislationLoader
from lex.legislation.models import LegislationType
from lex.legislation.parser import LegislationParser, LegislationSectionParser
from lex.legislation.parser.xml_to_text_parser import CLMLMarkdownParser
from tests.test_data.legislation_text_target import target_texts

parser = CLMLMarkdownParser()


def test_legislation_integration():
    """Test the full legislation parsing pipeline."""
    # Initialize components
    loader = LegislationLoader()
    legislation_parser = LegislationParser()
    legislation_section_parser = LegislationSectionParser()

    # Load and parse content
    legislations = []
    sections = []
    for legislation_soup in loader.load_content(
        years=[2024], types=[LegislationType.UKPGA], limit=10
    ):
        legislations.append(legislation_parser.parse_content(legislation_soup))
        sections.extend(legislation_section_parser.parse_content(legislation_soup))

    # Assertions
    assert len(legislations) > 0, "Should have parsed at least one legislation"
    assert len(sections) > 0, "Should have parsed at least one section"

    # Check that each legislation has basic required attributes
    for legislation in legislations:
        assert legislation is not None
        assert hasattr(legislation, "year")
        assert legislation.year == 2024

    # Check that each section has basic required attributes
    for section in sections:
        assert section is not None
        assert hasattr(section, "number")
        assert hasattr(section, "text")


outputs = [
    "\ta) after subsection (1) insert— \n\t1A) The reference in subsection (1) to encouraging low carbon electricity generation includes encouraging the continuation of, or an increase in, low carbon electricity generation by existing generating stations. , and ",
    "4) \n1) This section applies for the purposes of sections 1 to 3 and this section. Expressions relating to electricity \n2) A “licensed electricity supplier” is a person who holds an electricity supply licence. \n3) An “electricity supply licence” is a licence granted under section 6(1)(d) of the Electricity Act 1989. \n4) “GB domestic electricity supply” is the supply of electricity to premises that are domestic premises for the purposes of the relevant standard conditions (as they have effect from time to time). \n5) In subsection (4) “relevant standard conditions” are the conditions which are, by virtue of section 33(1) of the Utilities Act 2000, the standard conditions for the purposes of electricity supply licences. Expressions relating to gas \n6) A “licensed gas supplier” is a person who holds a gas supply licence. \n7) A “gas supply licence” is a licence granted under section 7A(1) of the Gas Act 1986. \n8) “Gas shipper” has the same meaning as in Part 1 of the Gas Act 1986 (see section 7A(11) of that Act). \n9) “GB domestic gas supply” is the supply of gas to premises that are domestic premises for the purposes of the relevant standard conditions (as they have effect from time to time). \n10) In subsection (9) “relevant standard conditions” are the conditions which are, by virtue of section 81(2) of the Utilities Act 2000, the standard conditions for the purposes of gas supply licences. Other expressions \n11) A reference to a charge for GB domestic electricity supply or GB domestic gas supply includes a reference to a charge that does not relate to electricity or gas supplied (such as a standing charge). ",
    "*Reduction of domestic energy bills in England, Wales and Scotland*\n\n\nSection 4) **Interpretation of sections 1 to 3**\n\n1) This section applies for the purposes of sections 1 to 3 and this section. Expressions relating to electricity \n2) A “licensed electricity supplier” is a person who holds an electricity supply licence. \n3) An “electricity supply licence” is a licence granted under section 6(1)(d) of the Electricity Act 1989. \n4) “GB domestic electricity supply” is the supply of electricity to premises that are domestic premises for the purposes of the relevant standard conditions (as they have effect from time to time). \n5) In subsection (4) “relevant standard conditions” are the conditions which are, by virtue of section 33(1) of the Utilities Act 2000, the standard conditions for the purposes of electricity supply licences. Expressions relating to gas \n6) A “licensed gas supplier” is a person who holds a gas supply licence. \n7) A “gas supply licence” is a licence granted under section 7A(1) of the Gas Act 1986. \n8) “Gas shipper” has the same meaning as in Part 1 of the Gas Act 1986 (see section 7A(11) of that Act). \n9) “GB domestic gas supply” is the supply of gas to premises that are domestic premises for the purposes of the relevant standard conditions (as they have effect from time to time). \n10) In subsection (9) “relevant standard conditions” are the conditions which are, by virtue of section 81(2) of the Utilities Act 2000, the standard conditions for the purposes of gas supply licences. Other expressions \n11) A reference to a charge for GB domestic electricity supply or GB domestic gas supply includes a reference to a charge that does not relate to electricity or gas supplied (such as a standing charge). ",
    "*Reduction of domestic energy bills in Northern Ireland*\n\n\nSection 5) **Domestic energy price reduction schemes for Northern Ireland**\n\n1) The Secretary of State may establish a domestic electricity price reduction scheme for Northern Ireland. \n2) A “domestic electricity price reduction scheme for Northern Ireland” is a scheme (including any other related arrangements) that makes provision for and in connection with— \n\ta) reducing the amount that would otherwise be charged for NI domestic electricity supply by licensed electricity suppliers who are parties to the scheme, and \n\tb) making payments to those suppliers in respect of those reductions in charges. \n3) The Secretary of State may establish a domestic gas price reduction scheme for Northern Ireland. \n4) A “domestic gas price reduction scheme for Northern Ireland” is a scheme (including any other related arrangements) that makes provision for and in connection with— \n\ta) reducing the amount that would otherwise be charged for NI domestic gas supply by licensed gas suppliers who are parties to the scheme, and \n\tb) making payments to those suppliers in respect of those reductions in charges. \n5) The Secretary of State may modify or revoke a domestic electricity or gas price reduction scheme for Northern Ireland. \n6) But if the scheme includes provision about modification or revocation of the scheme, the Secretary of State’s power to modify or revoke it is subject to that provision. \n7) Any such provision of the scheme does not prevent the Secretary of State from modifying the scheme if— \n\ta) the Secretary of State considers that a licensed electricity supplier or licensed gas supplier may make, or has made, arrangements whose primary purpose is to increase payments to the supplier under the scheme, and \n\tb) the purpose of the modification of the scheme is to prevent the increased payments or require repayment of increased payments. \n8) For provision about time limits on the exercise of the powers conferred by this section, see Schedule 6. ",
    "*Reducing the price of electricity*\n\n\nSection 18) **Contracts for difference**\n\n1) The Energy Act 2013 is amended as follows. \n2) In section 6 (power to make regulations about contracts for difference for the purpose of encouraging low carbon electricity generation)— \n\ta) after subsection (1) insert— \n\t1A) The reference in subsection (1) to encouraging low carbon electricity generation includes encouraging the continuation of, or an increase in, low carbon electricity generation by existing generating stations. , and \n\tb) in subsection (8), after paragraph (a) insert— \n\t\taa) the first regulations made after the passing of the Energy Prices Act 2022 which make provision falling within each of the sections mentioned in paragraph (a); . \n3) In section 7 (designation of a CFD counterparty), in subsection (5), omit the words from “, but only” to the end. \n4) In section 17 (payments to electricity suppliers), after subsection (2) insert— \n2A) Regulations may make provision imposing on an electricity supplier who receives a payment from a CFD counterparty a requirement to secure that customers of the electricity supplier receive, by a time specified in the regulations, such benefit from the payment as may be specified in or determined in accordance with the regulations. \n5) In section 19 (information and advice)— \n\ta) in subsection (2)— \n\t\ti) in paragraph (c), after “the Northern Ireland system operator” insert “, an electricity supplier” , \n\t\tii) after paragraph (c) insert— \n\t\t\tca) for the Authority to require information to be provided to it by a CFD counterparty or electricity suppliers; \n\t\t\tcb) for the Northern Ireland Authority for Utility Regulation to require information to be provided to it by a CFD counterparty or electricity suppliers; , and \n\t\tiii) in paragraph (e), after “to it by” insert “the Authority, the Northern Ireland Authority for Utility Regulation,” , and \n\tb) in subsection (4), at the beginning insert “Except as provided by regulations,” . ",
    "## PART 2\n## WORKS PROVISIONS\n\n*Principal Powers*\n\n\nSection 6) **Power to construct and maintain works**\n\n1) Network Rail may construct and maintain the scheduled works. \n2) Subject to article 7 (power to deviate) the scheduled works may only be constructed in the lines or situations shown on the deposited plans and in accordance with the levels shown on the deposited sections. \n3) Subject to paragraph (5) , Network Rail may carry out and maintain such of the following works as may be necessary or expedient for the purposes of, or for purposes ancillary to, the construction of the scheduled works, namely— \n\ta) electrical equipment, signalling and permanent way works; \n\tb) hoardings and fencing, ramps, means of access and footpaths, bridleways and cycle tracks; \n\tc) embankments, cuttings, aprons, abutments, retaining walls, wing walls and culverts; \n\td) works to install or alter the position of apparatus, including mains, sewers, drains and cables; \n\te) works to alter or remove any structure erected upon any highway or adjoining land; \n\tf) landscaping and other works to mitigate any adverse effects of the construction maintenance or operation of the scheduled works; \n\tg) works for the benefit or protection of premises affected by the scheduled works; \n\th) works to alter the course of, or otherwise interfere with, a watercourse other than a navigable watercourse; and \n\ti) works to erect and construct offices and other buildings, machinery, apparatus, works and conveniences, \n4) Subject to paragraph (5) , Network Rail may carry out and maintain such other works (of whatever nature) as may be necessary or expedient for the purposes of, or for purposes ancillary to, the construction of the authorised works. \n5) Paragraphs (3) and (4) only authorise the carrying out or maintenance of works outside the limits of deviation if such works are carried out on— \n\ta) land specified in columns (1) and (2) of Schedule 2 (ancillary acquisition of land) for the purposes specified in column (3) of that Schedule; \n\tb) land specified in columns (1) and (2) of Schedule 3 (land in which only new rights etc. may be acquired) for the purposes specified in column (3) of that Schedule; or \n\tc) land specified in columns (1) and (2) of Schedule 4 (land of which temporary possession may be taken) for the purposes specified in column (3) of that Schedule relating to the authorised works specified in column (4) of that Schedule. \n\nSection 7) **Power to deviate**\nIn constructing or maintaining any of the scheduled works, Network Rail may— \n\ta) deviate laterally from the lines or situations shown on the deposited plans to the extent of the limits of deviation for that work; and \n\tb) deviate vertically from the levels shown on the deposited sections— \n\t\ti) to any extent upwards for Work No. 3 in accordance with the deposited plan and for all other Works not exceeding 1.5 metres; or \n\t\tii) to any extent downwards as may be found to be necessary or convenient. ",
    "Section 1) **Great British Energy**\n\n1) The Secretary of State may by notice designate a company as Great British Energy. \n2) A company may be designated under this section only if— \n\ta) it is limited by shares, and \n\tb) it is wholly owned by the Crown. \n3) A notice under subsection (1) — \n\ta) must specify the time from which the designation has effect, and \n\tb) must be published by the Secretary of State as soon as reasonably practicable after the notice is given. \n4) The designation of a company terminates— \n\ta) if the company ceases to be wholly owned by the Crown, or \n\tb) if the Secretary of State revokes the designation by notice. \n5) A notice under subsection (4) (b) — \n\ta) must specify the time from which the revocation has effect, and \n\tb) must be published by the Secretary of State as soon as reasonably practicable after the notice is given. \n6) For the purposes of this section a company is wholly owned by the Crown if each share in the company is held by— \n\ta) a Minister of the Crown, \n\tb) a company which is wholly owned by the Crown, or \n\tc) a nominee of a person falling within paragraph (a) or (b) . \n7) Great British Energy is exempt from the requirements of the Companies Act 2006 relating to the use of “limited” as part of its name. \n8) In this section — \n\t- “company” means a company registered under the Companies Act 2006 ;\n\t- “Minister of the Crown” has the same meaning as in the Ministers of the Crown Act 1975 (see section 8(1) of that Act).",
    "Section 10) **Extent, commencement and short title**\n\n1) This Act extends to England and Wales, Scotland and Northern Ireland. \n2) This Act comes into force on the day on which it is passed. \n3) This Act may be cited as the Great British Energy Act 2025. ",
]


@pytest.mark.parametrize("test_file_number", list(range(1, 9)))
def test_legislation_parsing(test_file_number):
    """Test CLMLMarkdownParser against individual test XML files."""

    expected_output = outputs[test_file_number - 1]
    # Load the XML file
    soup = load_xml_file_to_soup(f"tests/test_data/legislation_test_{test_file_number}.xml")

    # Parse with CLMLMarkdownParser
    result = parser.parse_element(soup).lstrip("\n")

    # Assert the output matches expected
    assert result == expected_output, (
        f"Parser output for legislation_test_{test_file_number}.xml does not match expected output"
    )


urls = [
    "https://www.legislation.gov.uk/ukpga/1997/34/data.xml",
    "https://www.legislation.gov.uk/ukcm/2007/1/data.xml",
    "https://www.legislation.gov.uk/wsi/2004/3054/data.xml",
    "https://www.legislation.gov.uk/asc/2024/4/data.xml",
    "https://www.legislation.gov.uk/asp/2017/5/data.xml",
    "https://www.legislation.gov.uk/ukcm/2003/1/data.xml",
    "https://www.legislation.gov.uk/ukla/2024/1/data.xml",
    "https://www.legislation.gov.uk/nisi/1990/1509/data.xml",
    "https://www.legislation.gov.uk/eudn/2019/2213/data.xml",
    "https://www.legislation.gov.uk/wsi/2007/580/data.xml",
    "https://www.legislation.gov.uk/anaw/2019/4/data.xml",
    "https://www.legislation.gov.uk/eudr/2018/2057/data.xml",
    "https://www.legislation.gov.uk/uksi/2023/1432/data.xml",
    "https://www.legislation.gov.uk/uksi/2015/1911/data.xml",
]


client = HttpClient()


@pytest.mark.parametrize("url,target_text", zip(urls, target_texts))
def test_legislation_parsing_integration(url, target_text):
    """Test CLMLMarkdownParser against individual test XML files."""
    # Load the XML file
    response = client.get(url)
    soup = BeautifulSoup(response.text, "xml")

    parser = LegislationSectionParser()
    provisions = parser.parse_content(soup)
    texts = [provision.text for provision in provisions]

    for text, target_text in zip(texts, target_text):
        assert text == target_text, f"Parser output for {url} does not match expected output"
