"""All on-screen and spoken content for Nordic Crypto #1 (newsreel site cut).

Facts only from newsletter issue #1. Brand is Nordic Crypto. The sign-off is
"The Nordic Crypto team". Jørgen's name appears only in the Nexa / Bitcoin
Unlimited conflict disclosure. Kaupr is named only as the source of the
GreenMerc story. Nothing in the narration says the programme is made with AI.
"""
# Calm male newsreader (NRK Gislefoss manner). Not RyanNeural at +20%.
VOICE = "en-GB-ThomasNeural"
RATE = "+2%"
ISSUE = "Issue #1"
DATES = "27 September – 2 October 2026"
DATES_SHORT = "27 Sep – 2 Oct 2026"
SITE = "jqrgen.github.io/nordic-crypto"

# story key -> lower third + graphic data
STORIES = {
 "s1": dict(section="TOP STORY", head="Crypto giant in new controversy: offered services in Europe without a licence",
            src="Realtid (Sweden) · 1 Oct", big="MiCA", kicker="BINANCE · EU CRYPTO RULES", art="stars"),
 "s2": dict(section="TOP STORY", head="Crypto giant skirts the rules in Europe and risks being thrown out",
            src="Dagens PS (Sweden) · 1 Oct", big="BINANCE", kicker="EU AUTHORITIES WANT TO KNOW HOW", art="stars"),
 "s3": dict(section="REGULATION", head="How Sweden can be used to finance nuclear weapons",
            src="Realtid (Sweden) · 2 Oct", big="SANCTIONS", kicker="SWEDEN'S WATCHDOG WARNS", art="globe"),
 "s4": dict(section="REGULATION", head="Here is where the risk of financing proliferation of weapons of mass destruction is highest",
            src="Finansinspektionen (Sweden) · 1 Oct", big="RISK REPORT", kicker="FINANSINSPEKTIONEN", art="globe"),
 "s7": dict(section="MARKETS & COMPANIES", head="GreenMerc cuts SEK 4.8 million a year as Northcrypto turns a profit",
            src="Kaupr (Sweden) · 30 Sep", big="SEK 4.8M", kicker="COST CUTS A YEAR · GREENMERC", art="bars"),
 "s8": dict(section="MARKETS & COMPANIES", head="Flying start for new crypto fund",
            src="Finansavisen (Norway) · 28 Sep · may require a subscription", big="+39%", kicker="SINCE AUGUST LAUNCH", art="bars"),
 "s9": dict(section="MARKETS & COMPANIES", head="Community and technology draw crypto investors: bitcoin's new rally celebrated at crypto event",
            src="Yle (Finland) · 27 Sep", big="COMMUNITY", kicker="& TECHNOLOGY · FINLAND", art="nodes"),
 "s5": dict(section="IN OTHER NEWS", head="Charged with selling drugs for cryptocurrency on the dark web",
            src="Aftenposten (Norway) · 2 Oct · may require a subscription", big="CHARGED", kicker="DARK WEB DRUG CASE · NORWAY", art="scan"),
 "s6": dict(section="IN OTHER NEWS", head="Reports: teenagers duct-taped a man in hunt for cryptocurrency",
            src="Sydsvenskan (Sweden) · 2 Oct", big="LUND", kicker="THREE TEENAGERS ARRESTED", art="scan"),
}
EVENTS = [("8 OCT", "Gothenburg", "Göteborg Bitcoin Meetup #49", "Ölrepubliken, 18:00"),
          ("14 OCT", "Oslo", "Crypto killer apps", "Polyteknisk Forening, 17:30 (paid entry)"),
          ("15 OCT", "Uppsala", "Uppsala Bitcoin Meetup", "Café Årummet, 17:30"),
          ("28 OCT", "Oslo", "Oslo Blockchain Meetup: Nexa", "Universitetsgata 2, 17:00")]
NEXA_DISCLOSURE = ("Disclosure (28 Oct): Jørgen (jQrgen), who runs Nordic Crypto, is the speaker, runs this meetup, "
                   "and works on Nexa at Bitcoin Unlimited.")
END_DISCLOSURE = "Nothing here is investment advice."
TICKER = ["NORDIC CRYPTO · ISSUE #1 · " + DATES_SHORT.upper(),
          "Binance under investigation for allegedly offering services in Europe without a MiCA licence (Realtid)",
          "Binance said it would leave Europe, but customers are still trading (Dagens PS)",
          "Sweden's financial watchdog: crypto-assets a top sanctions risk (Realtid / Finansinspektionen)",
          "Three Norwegians and a Swede charged in dark-web drug case (Aftenposten)",
          "Three teenagers arrested in Lund in hunt for crypto (Sydsvenskan)",
          "GreenMerc cuts SEK 4.8 million a year as Northcrypto turns a profit (Kaupr)",
          "New crypto fund up 39 percent since August launch (Finansavisen)",
          "Bitcoin's new rally celebrated at Finnish crypto event (Yle)",
          "ON THE CALENDAR: 8 Oct Gothenburg · 14 Oct Oslo · 15 Oct Uppsala · 28 Oct Oslo",
          "All stories at " + SITE]

# spoken narration per voiced segment
VO = {
 "open_a": "Good evening, and welcome to Nordic Crypto. This is issue number one, with the Nordic crypto news that mattered "
           "from the 27th of September to the 2nd of October, 2026.",
 "open_b": "Tonight: Binance under scrutiny over Europe's new crypto rules. Sweden's financial watchdog issues a crypto sanctions warning. "
           "And the meetups coming up across the region. Nordic Crypto gathers crypto, bitcoin and blockchain news from Norway, Sweden, "
           "Denmark, Finland and Iceland, with a link to every original source.",
 "s1": "Our top story tonight. Binance is under investigation for allegedly offering services in Europe without the licence "
       "required under the EU's new crypto rules, known as MiCA. That's from Realtid in Sweden.",
 "s2": "Dagens PS, also in Sweden, reports that Binance said it would leave Europe, but customers are still trading. "
       "EU financial authorities now want to know how.",
 "s3": "Realtid reports that Sweden's financial watchdog says crypto-assets and illegal financial networks pose the biggest risk "
       "of Iran and North Korea dodging sanctions through Sweden.",
 "s4": "Finansinspektionen's new risk assessment finds that weapons of mass destruction are most likely to be financed "
       "through illegal financial activity and crypto-assets.",
 "s7": "Kaupr reports that GreenMerc is cutting costs by 4.8 million Swedish kronor a year while Northcrypto turns a profit, "
       "with spending redirected to the banking offer Trijo One.",
 "s8": "In Norway, Finansavisen writes that Joakim Hannisdahl's new crypto fund, built on a model that did well in backtesting, "
       "is up 39 percent since it launched in August.",
 "s9": "And from Yle in Finland: at a Finnish crypto event, investors said community and technology are what draw them to crypto, "
       "as bitcoin rallied again.",
 "s5": "In Norway, three Norwegians and a Swede have been charged in a large drug case with links abroad, involving drug sales "
       "on the dark web, paid for in cryptocurrency. That's according to the Southern Norway public prosecutor, via Aftenposten.",
 "s6": "And in Lund, Sydsvenskan reports that three teenagers have been arrested on suspicion of kidnapping. They are suspected "
       "of tying up a local man with duct tape to rob him of crypto.",
 "cal": "On the 8th of October, it's Göteborg Bitcoin Meetup number 49, at Ölrepubliken in Gothenburg. On the 14th, Crypto killer apps, "
        "at Polyteknisk Forening in Oslo, with paid entry. On the 15th, the Uppsala Bitcoin Meetup, at Café Årummet. "
        "And on the 28th of October, Oslo Blockchain Meetup, on Nexa. A disclosure: Jørgen, who runs Nordic Crypto, is the speaker, "
        "runs this meetup, and works on Nexa at Bitcoin Unlimited. "
        "More events, including Stockholm and Helsinki in November, are in the calendar.",
 "signoff": "And that's Nordic Crypto for this week. All the stories, the events calendar and a who's who of Nordic crypto are on "
            "the Nordic Crypto website. If you spot a mistake, or a story we missed, use the tip form. "
            "Nothing here is investment advice. Until next week. The Nordic Crypto team. Good night.",
}

# timeline: (name, kind, extra). Bumpers have fixed length; voiced segments last voice + pad.
TIMELINE = [
 ("bumper", "bumper", {}),
 ("open_a", "title", {}),
 ("open_b", "tonight", {}),
 ("b_top", "section", {"label": "TOP STORY", "sub": "Binance and the EU's crypto rules (MiCA)"}),
 ("s1", "story", {}), ("s2", "story", {}),
 ("b_reg", "section", {"label": "REGULATION", "sub": "Sanctions and weapons financing: Sweden's watchdog warns"}),
 ("s3", "story", {}), ("s4", "story", {}),
 ("b_mkt", "section", {"label": "MARKETS & COMPANIES", "sub": "Business and markets"}),
 ("s7", "story", {}), ("s8", "story", {}), ("s9", "story", {}),
 ("b_other", "section", {"label": "IN OTHER NEWS", "sub": "Quick-fire: crime"}),
 ("s5", "story", {}), ("s6", "story", {}),
 ("b_cal", "section", {"label": "ON THE CALENDAR", "sub": "Meetups coming up"}),
 ("cal", "calendar", {}),
 ("signoff", "end", {}),
]
SIGNOFF_CARD = "The Nordic Crypto team"
# Newsreel bumper matches the 5.5s jingle. Section stings are about 2.0s.
BUMPER_LEN = {"bumper": 5.5, "section": 2.0}
