"""All on-screen and spoken content for Nordic Crypto #2 (newsreel site cut).

Facts only from newsletter issue #2. Brand is Nordic Crypto. The sign-off is
"The Nordic Crypto team". Kaupr is named only as the source of the Ace Digital
story. The Socialist Left card is labelled Proposal. Nothing on screen or in
the narration says the programme is made with artificial intelligence.
"""
import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
import site_url
VOICE = "en-GB-ThomasNeural"
RATE = "+12%"
NUMBER = "2"
ISSUE = "Issue #2"
ISSUE_RIBBON = "ISSUE #2"
DATES = "5–12 October 2026"
DATES_SHORT = "5–12 Oct 2026"
BUG_LINE = "ISSUE #2 · 5–12 OCT 2026"
SITE = site_url.HOST

# story key -> lower third + graphic data. section is the red label on the card.
STORIES = {
 "s1": dict(section="NORWAY", head="Red Party proposes a temporary halt for new data centres",
            src="Stortinget (Norway) · 5 Oct", big="HALT", kicker="RED PARTY · LICENSING REGIME", art="globe"),
 "s2": dict(section="PROPOSAL", head="Socialist Left proposes a pause on new data centres",
            src="Stortinget (Norway) · 5 Oct", big="PROPOSAL", kicker="SOCIALIST LEFT · NOT A DECISION", art="globe"),
 "s3": dict(section="NORWAY", head="Arctic Core says crypto mining is income in a test phase",
            src="Ságat (Norway) · 7 Oct · may require a subscription", big="TEST", kicker="ARCTIC CORE · DATA CENTRE", art="nodes"),
 "s4": dict(section="MARKETS", head="Firi customers bought 16.1 million kroner more crypto than they sold",
            src="Finansavisen (Norway) · 5 Oct · may require a subscription", big="16.1M", kicker="KRONER NET BUYING · SEPTEMBER", art="bars"),
 "s5": dict(section="COMPANIES", head="Ace Digital reports a 6.3 million kroner third-quarter net profit",
            src="Kaupr (Norway) · 5 Oct", big="6.3M", kicker="Q3 NET PROFIT · ACE DIGITAL", art="bars"),
 "s6": dict(section="SWEDEN", head="Finansinspektionen warns against thirty more unlicensed firms",
            src="Nyheter24 (Sweden) · 6 Oct", big="30", kicker="MORE WARNINGS · 227 THIS YEAR", art="scan"),
 "s7": dict(section="EU RULES", head="AMLA sends three draft standards to the European Commission",
            src="Finansinspektionen (Sweden) · 5 Oct", big="AMLA", kicker="DRAFT STANDARDS · CRYPTO RULES", art="stars"),
}
END_DISCLOSURE = "Nothing here is investment advice."
# Kaupr is not named in the ticker. It appears only as the source on the Ace Digital card.
TICKER = ["NORDIC CRYPTO · ISSUE #2 · " + DATES_SHORT.upper(),
          "Red Party proposes a temporary halt for new data centres, with a licensing regime (Stortinget)",
          "Socialist Left proposes a pause on new data centres: a proposal, not a decision (Stortinget)",
          "Arctic Core says crypto mining earns income during a test phase (Ságat)",
          "Firi customers bought 16.1 million kroner more crypto than they sold in September (Finansavisen)",
          "Ace Digital reports an unaudited third-quarter net profit of 6.3 million kroner and no debt",
          "Finansinspektionen warns against thirty more unlicensed firms; 227 warnings this year (Nyheter24)",
          "AMLA sends three draft anti-money-laundering standards to the European Commission (Finansinspektionen)",
          "All stories at " + SITE]

# Spoken narration, word for word from the editor-approved script.
VO = {
 "open_a": "Good evening, and welcome to Nordic Crypto. This is issue number two, with the Nordic crypto news from the 5th to the 12th of October, 2026.",
 "open_b": "Tonight: proposals in the Storting to pause new data centres. Sweden's financial watchdog names thirty more suspected fraud firms. And new EU anti-money-laundering standards that touch crypto.",
 "s1": "The Red Party has proposed in the Storting a temporary halt for new data centres, with a licensing regime. It argues that crypto-mining data centres get power ahead of local industry. None of the proposals singles out crypto. That's from Stortinget.",
 "s2": "Socialist Left Party members have also proposed a pause on new data centres and a national licensing system, and ask the government to report on how the Storting's call for a crypto-mining ban will be followed up. This is a proposal, not a decision.",
 "s3": "In Ságat, the data-centre company Arctic Core says it uses crypto mining to earn income during a test phase, but argues this does not change the character of the building it has a permit for.",
 "s4": "Finansavisen reports that customers of the Norwegian exchange Firi bought 16.1 million kroner more crypto than they sold in September. Bitcoin was the top buy.",
 "s5": "Kaupr reports that Ace Digital, listed on Euronext Growth Oslo, made an unaudited third-quarter net profit of 6.3 million kroner, and says it now has no debt.",
 "s6": "Nyheter24 reports that Finansinspektionen has warned against thirty more firms operating without a licence, some offering trading in crypto. That brings this year's warnings to 227.",
 "s7": "And Finansinspektionen reports that the EU's anti-money-laundering authority, AMLA, has sent three draft technical standards to the European Commission. They include rules for crypto-asset service providers, and still need the Commission's adoption.",
 "close": "That's all for issue number two. Every story, with a link to the original source, is at nordiccrypto.no. Nothing here is investment advice. From all of us: good night, from the Nordic Crypto team.",
}

TONIGHT = [
 ("NORWAY", "Proposals in the Storting to pause new data centres", "storting"),
 ("SWEDEN", "Sweden's financial watchdog names thirty more suspected fraud firms", "sweden"),
 ("EU RULES", "New EU anti-money-laundering standards that touch crypto", "anti-money"),
]

# timeline: (name, kind, extra). Bumpers have fixed length; voiced segments last voice + pad.
TIMELINE = [
 ("bumper", "bumper", {}),
 ("open_a", "title", {}),
 ("open_b", "tonight", {}),
 ("b_no", "section", {"label": "NORWAY", "sub": "Data centres, mining and the markets"}),
 ("s1", "story", {}), ("s2", "story", {}), ("s3", "story", {}), ("s4", "story", {}), ("s5", "story", {}),
 ("b_se", "section", {"label": "SWEDEN & EU", "sub": "Fraud warnings and anti-money-laundering standards"}),
 ("s6", "story", {}), ("s7", "story", {}),
 ("close", "end", {}),
]
SIGNOFF_CARD = "The Nordic Crypto team"
END_HEAD = "THAT'S ALL FOR ISSUE NUMBER TWO"
# Newsreel bumper matches the 5.5s jingle. Section stings are about 2.0s.
BUMPER_LEN = {"bumper": 5.5, "section": 2.0, "countries": 4.0}
THUMB_HEAD = "Data-centre halt proposals and new fraud warnings in Sweden"
