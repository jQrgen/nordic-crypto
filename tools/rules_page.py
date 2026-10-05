#!/usr/bin/env python3
"""'How the rules are made' (rules/) for Crypto Nordic, called by build.py -> build_rules(ctx) for every language.
Data: rules.json (sources + nodes, English proper names). Page text: STR below (en, nn, nb, sv, da, fi, is).
Editor review: while rules.json "review" is "pending", the public build writes a short placeholder page (so links from
the org chart, industry map and about page never break) and only the preview build (--preview) shows the full page.
Claims and their sources: research/rules-claims-2026-10-03.md (public-claim-check workflow).
No third-party scripts; the flowchart is inline SVG + CSS, animation off under prefers-reduced-motion; the ordered list
below the diagram is the full text version (the SVG is aria-hidden)."""
import datetime, json, os

STR = {
"en": dict(title="How the rules are made", desc="How EU crypto rules (MiCA, AMLR, DORA) become law in Norway, Sweden, Denmark, Finland and Iceland, and who supervises and enforces them – with a source for every step.",
  lead="A simplified map of how crypto rules travel from Brussels to the five Nordic countries, and who supervises and enforces them. Every box links to its legal source and, where we have one, to the entry in our org chart. Choose a country to follow its route.",
  s1="EU level", s1p="The European Commission proposes a regulation; the European Parliament and the Council adopt it under the ordinary legislative procedure. ESMA and EBA then fill in details and supervise parts of it.",
  s2="Into national law", s2eu="Sweden, Denmark and Finland are EU members: EU regulations are binding and directly applicable there. A national act adds what the regulation leaves to each country, such as which authority is in charge.",
  s2eea="The EEA Joint Committee decided on 20 February 2025 (Decision No 41/2025) to incorporate MiCA into the EEA Agreement; Norway and Iceland then gave it effect in national law.",
  s3="Parliament and ministry", s3p="As a rule, the ministry responsible for financial markets prepares the bill and the national parliament adopts it.",
  s4="Supervisor", s4p="The national competent authority authorises crypto-asset service providers and supervises them.",
  s5="Enforcement", s5p="Suspicious transactions are reported to the financial intelligence unit (FIU), which is part of the police or prosecution service. In each country the national tax authority is responsible for taxation, including of crypto-assets.",
  propose="proposes", adopt="adopts", applies="applies from {d}", law="National act", parliament="Parliament", ministry="Ministry", supervisor="Supervisor", fiu="FIU / police", tax="Tax authority",
  act_mica="Markets in crypto-assets: licences for crypto-asset service providers, rules for issuers and stablecoins.", act_tfr="'Travel rule': information about sender and recipient must follow crypto transfers.",
  act_amlr="EU anti-money-laundering rulebook, including crypto-asset service providers.", act_dora="Digital operational resilience (ICT risk) for financial firms, including crypto-asset service providers.",
  ag_esma="Keeps the MiCA register and drafts technical standards.", ag_eba="Supervises issuers of significant stablecoins (asset-referenced and e-money tokens).",
  country="Country", all="All", src="source", chart="org chart", diagram="Diagram (the full text version follows below)", eea="EEA route", eu_route="EU member",
  caveat="Simplified overview, not legal advice. Dates are when the EU regulation applies in the EU; national dates can differ (in the EEA they follow incorporation). Checked {d}.",
  pending="Awaiting editor review – content may change.", placeholder="This page is being prepared and is awaiting editor review. Meanwhile, see the regulation overview in the org chart.",
  back="← Who's who", see_map="Industry map", general="General description", r12_dk="Suspicious transactions are reported to Hvidvasksekretariatet, the Danish FIU within NSK. There is no separate crypto tax act; Skattestyrelsen applies the general tax rules to crypto-assets.", r13_fi="Act 402/2024 supplements MiCA; under its section 2, Finanssivalvonta supervises compliance.", r14_fi="Suspicious transactions are reported to the Financial Intelligence Unit (Rahanpesun selvittelykeskus) within the National Bureau of Investigation (Acts 444/2017 and 445/2017)."),
"nb": dict(title="Slik blir reglene til", desc="Hvordan EUs kryptoregler (MiCA, AMLR, DORA) blir lov i Norge, Sverige, Danmark, Finland og Island, og hvem som fører tilsyn og håndhever dem – med kilde for hvert steg.",
  lead="Et forenklet kart over hvordan kryptoregler går fra Brussel til de fem nordiske landene, og hvem som fører tilsyn og håndhever dem. Hver boks lenker til den rettslige kilden og, der vi har en, til oppføringen i hvem er hvem. Velg et land for å følge veien.",
  s1="EU-nivå", s1p="Europakommisjonen foreslår en forordning; Europaparlamentet og Rådet vedtar den etter den ordinære lovgivningsprosedyren. ESMA og EBA fyller deretter ut detaljer og fører tilsyn med deler av den.",
  s2="Inn i nasjonal rett", s2eu="Sverige, Danmark og Finland er EU-medlemmer: EU-forordninger er bindende og gjelder direkte der. En nasjonal lov legger til det forordningen overlater til hvert land, for eksempel hvilken myndighet som har ansvaret.",
  s2eea="EØS-komiteen vedtok 20. februar 2025 (beslutning nr. 41/2025) å ta MiCA inn i EØS-avtalen; Norge og Island gjennomførte den deretter i nasjonal rett.",
  s3="Storting og departement", s3p="Som hovedregel forbereder departementet med ansvar for finansmarkedene lovforslaget, og nasjonalforsamlingen vedtar det.",
  s4="Tilsyn", s4p="Den nasjonale vedkommende myndigheten gir tillatelse til tilbydere av kryptoeiendelstjenester og fører tilsyn med dem.",
  s5="Håndheving", s5p="Mistenkelige transaksjoner rapporteres til finansetterretningsenheten (FIU), som er en del av politiet eller påtalemyndigheten. I hvert land har den nasjonale skattemyndigheten ansvaret for beskatning, også av kryptoeiendeler.",
  propose="foreslår", adopt="vedtar", applies="gjelder fra {d}", law="Nasjonal lov", parliament="Nasjonalforsamling", ministry="Departement", supervisor="Tilsyn", fiu="FIU / politi", tax="Skattemyndighet",
  act_mica="Markeder for kryptoeiendeler: tillatelse for tilbydere av kryptoeiendelstjenester, regler for utstedere og stablecoins.", act_tfr="«Reiseregelen»: opplysninger om avsender og mottaker skal følge kryptooverføringer.",
  act_amlr="EUs regelverk mot hvitvasking, også for tilbydere av kryptoeiendelstjenester.", act_dora="Digital operasjonell motstandsdyktighet (IKT-risiko) for finansforetak, også tilbydere av kryptoeiendelstjenester.",
  ag_esma="Fører MiCA-registeret og utarbeider tekniske standarder.", ag_eba="Fører tilsyn med utstedere av vesentlige stablecoins (aktivareferte tokener og e-pengetokener).",
  country="Land", all="Alle", src="kilde", chart="hvem er hvem", diagram="Diagram (full tekstversjon følger under)", eea="EØS-veien", eu_route="EU-medlem",
  caveat="Forenklet oversikt, ikke juridisk rådgivning. Datoene er når EU-forordningen gjelder i EU; nasjonale datoer kan være andre (i EØS følger de innlemmelsen). Kontrollert {d}.",
  pending="Venter på redaktørens gjennomgang – innholdet kan endres.", placeholder="Denne siden er under arbeid og venter på redaktørens gjennomgang. Se reguleringsoversikten i hvem er hvem i mellomtiden.",
  back="← Hvem er hvem", see_map="Bransjekart", general="Generell beskrivelse", r12_dk="Mistenkelige transaksjoner rapporteres til Hvidvasksekretariatet, den danske finansetterretningsenheten (FIU) i NSK. Det finnes ingen egen skattelov for krypto; Skattestyrelsen bruker de alminnelige skattereglene på kryptoeiendeler.", r13_fi="Lov 402/2024 supplerer MiCA; etter lovens § 2 fører Finanssivalvonta tilsyn med at reglene følges.", r14_fi="Mistenkelige transaksjoner rapporteres til finansetterretningsenheten (Rahanpesun selvittelykeskus) i det finske sentralkriminalpolitiet (lov 444/2017 og 445/2017)."),
"nn": dict(title="Slik blir reglane til", desc="Korleis kryptoreglane til EU (MiCA, AMLR, DORA) blir lov i Noreg, Sverige, Danmark, Finland og Island, og kven som fører tilsyn og handhevar dei – med kjelde for kvart steg.",
  lead="Eit forenkla kart over korleis kryptoreglar går frå Brussel til dei fem nordiske landa, og kven som fører tilsyn og handhevar dei. Kvar boks lenkjer til den rettslege kjelda og, der vi har ei, til oppføringa i kven er kven. Vel eit land for å følgje vegen.",
  s1="EU-nivå", s1p="Europakommisjonen føreslår ei forordning; Europaparlamentet og Rådet vedtek ho etter den ordinære lovgivingsprosedyren. ESMA og EBA fyller deretter ut detaljar og fører tilsyn med delar av henne.",
  s2="Inn i nasjonal rett", s2eu="Sverige, Danmark og Finland er EU-medlemer: EU-forordningar er bindande og gjeld direkte der. Ei nasjonal lov legg til det forordninga overlèt til kvart land, til dømes kva styresmakt som har ansvaret.",
  s2eea="EØS-komiteen vedtok 20. februar 2025 (avgjerd nr. 41/2025) å ta MiCA inn i EØS-avtalen; Noreg og Island gjennomførte henne deretter i nasjonal rett.",
  s3="Storting og departement", s3p="Som hovudregel førebur departementet med ansvar for finansmarknadene lovforslaget, og nasjonalforsamlinga vedtek det.",
  s4="Tilsyn", s4p="Den nasjonale vedkomande styresmakta gir løyve til tilbydarar av kryptoeigedelstenester og fører tilsyn med dei.",
  s5="Handheving", s5p="Mistenkjelege transaksjonar blir rapporterte til finansetterretningseininga (FIU), som er ein del av politiet eller påtalemakta. I kvart land har den nasjonale skattestyresmakta ansvaret for skattlegging, også av kryptoeigedelar.",
  propose="føreslår", adopt="vedtek", applies="gjeld frå {d}", law="Nasjonal lov", parliament="Nasjonalforsamling", ministry="Departement", supervisor="Tilsyn", fiu="FIU / politi", tax="Skattestyresmakt",
  act_mica="Marknader for kryptoeigedelar: løyve for tilbydarar av kryptoeigedelstenester, reglar for utferdarar og stablecoins.", act_tfr="«Reiseregelen»: opplysningar om avsendar og mottakar skal følgje kryptooverføringar.",
  act_amlr="Regelverket til EU mot kvitvasking, òg for tilbydarar av kryptoeigedelstenester.", act_dora="Digital operasjonell motstandsdyktigheit (IKT-risiko) for finansføretak, òg tilbydarar av kryptoeigedelstenester.",
  ag_esma="Fører MiCA-registeret og utarbeider tekniske standardar.", ag_eba="Fører tilsyn med utferdarar av vesentlege stablecoins (aktivareferte tokenar og e-pengetokenar).",
  country="Land", all="Alle", src="kjelde", chart="kven er kven", diagram="Diagram (full tekstversjon følgjer under)", eea="EØS-vegen", eu_route="EU-medlem",
  caveat="Forenkla oversikt, ikkje juridisk rådgiving. Datoane er når EU-forordninga gjeld i EU; nasjonale datoar kan vere andre (i EØS følgjer dei innlemminga). Kontrollert {d}.",
  pending="Ventar på gjennomgang frå redaktøren – innhaldet kan endrast.", placeholder="Denne sida er under arbeid og ventar på gjennomgang frå redaktøren. Sjå reguleringsoversikta i kven er kven i mellomtida.",
  back="← Kven er kven", see_map="Bransjekart", general="Generell skildring", r12_dk="Mistenkjelege transaksjonar blir rapporterte til Hvidvasksekretariatet, den danske finansetterretningseininga (FIU) i NSK. Det finst inga eiga skattelov for krypto; Skattestyrelsen bruker dei alminnelege skattereglane på kryptoeigedelar.", r13_fi="Lov 402/2024 utfyller MiCA; etter § 2 i lova fører Finanssivalvonta tilsyn med at reglane blir følgde.", r14_fi="Mistenkjelege transaksjonar blir rapporterte til finansetterretningseininga (Rahanpesun selvittelykeskus) i det finske sentralkriminalpolitiet (lov 444/2017 og 445/2017)."),
"sv": dict(title="Så blir reglerna till", desc="Hur EU:s kryptoregler (MiCA, AMLR, DORA) blir lag i Norge, Sverige, Danmark, Finland och Island, och vem som utövar tillsyn och upprätthåller dem – med källa för varje steg.",
  lead="En förenklad karta över hur kryptoregler går från Bryssel till de fem nordiska länderna, och vem som utövar tillsyn och upprätthåller dem. Varje ruta länkar till den rättsliga källan och, där vi har en, till posten i vem är vem. Välj ett land för att följa vägen.",
  s1="EU-nivå", s1p="Europeiska kommissionen föreslår en förordning; Europaparlamentet och rådet antar den enligt det ordinarie lagstiftningsförfarandet. Esma och EBA fyller sedan i detaljer och utövar tillsyn över delar av den.",
  s2="In i nationell rätt", s2eu="Sverige, Danmark och Finland är EU-medlemmar: EU-förordningar är bindande och direkt tillämpliga där. En nationell lag lägger till det som förordningen överlåter åt varje land, till exempel vilken myndighet som ansvarar.",
  s2eea="EES-kommittén beslutade den 20 februari 2025 (beslut nr 41/2025) att införliva MiCA i EES-avtalet; Norge och Island genomförde den sedan i nationell rätt.",
  s3="Riksdag och departement", s3p="Som regel bereder det ministerium som ansvarar för finansmarknaderna lagförslaget, och det nationella parlamentet antar det.",
  s4="Tillsyn", s4p="Den nationella behöriga myndigheten ger tillstånd till leverantörer av kryptotillgångstjänster och utövar tillsyn över dem.",
  s5="Upprätthållande", s5p="Misstänkta transaktioner rapporteras till finansunderrättelseenheten (FIU), som är en del av polisen eller åklagarväsendet. I varje land ansvarar den nationella skattemyndigheten för beskattningen, även av kryptotillgångar.",
  propose="föreslår", adopt="antar", applies="gäller från {d}", law="Nationell lag", parliament="Parlament", ministry="Departement", supervisor="Tillsyn", fiu="FIU / polis", tax="Skattemyndighet",
  act_mica="Marknader för kryptotillgångar: tillstånd för leverantörer av kryptotillgångstjänster, regler för emittenter och stablecoins.", act_tfr="”Reseregeln”: uppgifter om avsändare och mottagare ska följa med kryptoöverföringar.",
  act_amlr="EU:s regelverk mot penningtvätt, även för leverantörer av kryptotillgångstjänster.", act_dora="Digital operativ motståndskraft (IKT-risk) för finansiella företag, även leverantörer av kryptotillgångstjänster.",
  ag_esma="För MiCA-registret och utarbetar tekniska standarder.", ag_eba="Utövar tillsyn över emittenter av betydande stablecoins (tillgångsanknutna token och e-pengatoken).",
  country="Land", all="Alla", src="källa", chart="vem är vem", diagram="Diagram (fullständig textversion följer nedan)", eea="EES-vägen", eu_route="EU-medlem",
  caveat="Förenklad översikt, inte juridisk rådgivning. Datumen anger när EU-förordningen gäller i EU; nationella datum kan skilja sig (i EES följer de införlivandet). Kontrollerad {d}.",
  pending="Väntar på redaktörens granskning – innehållet kan ändras.", placeholder="Den här sidan håller på att tas fram och väntar på redaktörens granskning. Se under tiden regleringsöversikten i vem är vem.",
  back="← Vem är vem", see_map="Branschkarta", general="Allmän beskrivning", r12_dk="Misstänkta transaktioner rapporteras till Hvidvasksekretariatet, Danmarks finansunderrättelseenhet (FIU) inom NSK. Det finns ingen särskild skattelag för kryptotillgångar; Skattestyrelsen tillämpar de allmänna skattereglerna på kryptotillgångar.", r13_fi="Lag 402/2024 kompletterar MiCA; enligt lagens 2 § övervakar Finanssivalvonta att reglerna följs.", r14_fi="Misstänkta transaktioner rapporteras till finansunderrättelseenheten (Rahanpesun selvittelykeskus) inom den finska centralkriminalpolisen (lag 444/2017 och 445/2017)."),
"da": dict(title="Sådan bliver reglerne til", desc="Hvordan EU's kryptoregler (MiCA, AMLR, DORA) bliver lov i Norge, Sverige, Danmark, Finland og Island, og hvem der fører tilsyn med og håndhæver dem – med kilde til hvert trin.",
  lead="Et forenklet kort over, hvordan kryptoregler går fra Bruxelles til de fem nordiske lande, og hvem der fører tilsyn med og håndhæver dem. Hver boks linker til den retlige kilde og, hvor vi har et, til opslaget i hvem er hvem. Vælg et land for at følge vejen.",
  s1="EU-niveau", s1p="Europa-Kommissionen foreslår en forordning; Europa-Parlamentet og Rådet vedtager den efter den almindelige lovgivningsprocedure. ESMA og EBA udfylder derefter detaljer og fører tilsyn med dele af den.",
  s2="Ind i national ret", s2eu="Sverige, Danmark og Finland er EU-medlemmer: EU-forordninger er bindende og gælder umiddelbart dér. En national lov tilføjer det, forordningen overlader til hvert land, for eksempel hvilken myndighed der har ansvaret.",
  s2eea="EØS-Udvalget besluttede den 20. februar 2025 (afgørelse nr. 41/2025) at indarbejde MiCA i EØS-aftalen; Norge og Island gennemførte den derefter i national ret.",
  s3="Parlament og ministerium", s3p="Som hovedregel forbereder det ministerium, der har ansvaret for de finansielle markeder, lovforslaget, og det nationale parlament vedtager det.",
  s4="Tilsyn", s4p="Den nationale kompetente myndighed giver tilladelse til udbydere af kryptoaktivtjenester og fører tilsyn med dem.",
  s5="Håndhævelse", s5p="Mistænkelige transaktioner indberettes til den finansielle efterretningsenhed (FIU), som er en del af politiet eller anklagemyndigheden. I hvert land er den nationale skattemyndighed ansvarlig for beskatningen, også af kryptoaktiver.",
  propose="foreslår", adopt="vedtager", applies="gælder fra {d}", law="National lov", parliament="Parlament", ministry="Ministerium", supervisor="Tilsyn", fiu="FIU / politi", tax="Skattemyndighed",
  act_mica="Markeder for kryptoaktiver: tilladelse til udbydere af kryptoaktivtjenester, regler for udstedere og stablecoins.", act_tfr="»Rejsereglen«: oplysninger om afsender og modtager skal følge med kryptooverførsler.",
  act_amlr="EU's regelsæt mod hvidvask, også for udbydere af kryptoaktivtjenester.", act_dora="Digital operationel modstandsdygtighed (IKT-risiko) for finansielle virksomheder, også udbydere af kryptoaktivtjenester.",
  ag_esma="Fører MiCA-registret og udarbejder tekniske standarder.", ag_eba="Fører tilsyn med udstedere af signifikante stablecoins (aktivbaserede tokens og e-pengetokens).",
  country="Land", all="Alle", src="kilde", chart="hvem er hvem", diagram="Diagram (fuld tekstversion følger nedenfor)", eea="EØS-vejen", eu_route="EU-medlem",
  caveat="Forenklet overblik, ikke juridisk rådgivning. Datoerne angiver, hvornår EU-forordningen gælder i EU; nationale datoer kan være andre (i EØS følger de optagelsen). Kontrolleret {d}.",
  pending="Afventer redaktørens gennemgang – indholdet kan ændre sig.", placeholder="Denne side er under udarbejdelse og afventer redaktørens gennemgang. Se imens reguleringsoverblikket i hvem er hvem.",
  back="← Hvem er hvem", see_map="Branchekort", general="Generel beskrivelse", r12_dk="Mistænkelige transaktioner indberettes til Hvidvasksekretariatet, Danmarks finansielle efterretningsenhed (FIU) i NSK. Der findes ingen særlig skattelov for krypto; Skattestyrelsen anvender de almindelige skatteregler på kryptoaktiver.", r13_fi="Lov 402/2024 supplerer MiCA; efter lovens § 2 fører Finanssivalvonta tilsyn med, at reglerne overholdes.", r14_fi="Mistænkelige transaktioner indberettes til den finansielle efterretningsenhed (Rahanpesun selvittelykeskus) i det finske centrale kriminalpoliti (lov 444/2017 og 445/2017)."),
"fi": dict(title="Näin säännöt syntyvät", desc="Miten EU:n kryptosäännöistä (MiCA, AMLR, DORA) tulee lakia Norjassa, Ruotsissa, Tanskassa, Suomessa ja Islannissa ja kuka niitä valvoo ja panee täytäntöön – jokaiselle vaiheelle lähde.",
  lead="Yksinkertaistettu kartta siitä, miten kryptosäännöt kulkevat Brysselistä viiteen Pohjoismaahan ja kuka niitä valvoo ja panee täytäntöön. Jokainen laatikko linkittää oikeudelliseen lähteeseensä ja, jos meillä on sellainen, toimijahakemiston merkintään. Valitse maa seurataksesi sen reittiä.",
  s1="EU-taso", s1p="Euroopan komissio tekee asetusehdotuksen; Euroopan parlamentti ja neuvosto hyväksyvät sen tavallisessa lainsäätämisjärjestyksessä. ESMA ja EBA täydentävät sen jälkeen yksityiskohtia ja valvovat osaa siitä.",
  s2="Kansalliseen lainsäädäntöön", s2eu="Ruotsi, Tanska ja Suomi ovat EU:n jäseniä: EU-asetukset ovat niissä velvoittavia ja suoraan sovellettavia. Kansallinen laki täydentää sen, minkä asetus jättää kunkin maan päätettäväksi, esimerkiksi sen, mikä viranomainen vastaa asiasta.",
  s2eea="ETA:n sekakomitea päätti 20. helmikuuta 2025 (päätös nro 41/2025) sisällyttää MiCA-asetuksen ETA-sopimukseen; Norja ja Islanti panivat sen sen jälkeen täytäntöön kansallisessa lainsäädännössään.",
  s3="Parlamentti ja ministeriö", s3p="Pääsääntöisesti rahoitusmarkkinoista vastaava ministeriö valmistelee lakiesityksen ja kansallinen parlamentti hyväksyy sen.",
  s4="Valvoja", s4p="Kansallinen toimivaltainen viranomainen myöntää toimiluvat kryptovarapalvelujen tarjoajille ja valvoo niitä.",
  s5="Täytäntöönpano", s5p="Epäilyttävistä liiketoimista ilmoitetaan rahanpesun selvittelykeskukselle (FIU), joka on osa poliisia tai syyttäjälaitosta. Kussakin maassa kansallinen veroviranomainen vastaa verotuksesta, myös kryptovarojen verotuksesta.",
  propose="ehdottaa", adopt="hyväksyy", applies="sovelletaan {d} alkaen", law="Kansallinen laki", parliament="Parlamentti", ministry="Ministeriö", supervisor="Valvoja", fiu="FIU / poliisi", tax="Veroviranomainen",
  act_mica="Kryptovaramarkkinat: toimiluvat kryptovarapalvelujen tarjoajille, säännöt liikkeeseenlaskijoille ja vakaakolikoille.", act_tfr="”Matkustussääntö”: lähettäjän ja vastaanottajan tietojen on kuljettava kryptosiirtojen mukana.",
  act_amlr="EU:n rahanpesun vastainen säännöstö, myös kryptovarapalvelujen tarjoajille.", act_dora="Digitaalinen häiriönsietokyky (ICT-riskit) rahoitusalan yrityksille, myös kryptovarapalvelujen tarjoajille.",
  ag_esma="Ylläpitää MiCA-rekisteriä ja laatii teknisiä standardeja.", ag_eba="Valvoo merkittävien vakaakolikoiden (omaisuusviitteisten tokenien ja sähkörahatokenien) liikkeeseenlaskijoita.",
  country="Maa", all="Kaikki", src="lähde", chart="toimijahakemisto", diagram="Kaavio (koko tekstiversio alla)", eea="ETA-reitti", eu_route="EU-jäsen",
  caveat="Yksinkertaistettu katsaus, ei oikeudellista neuvontaa. Päivämäärät kertovat, milloin EU-asetusta sovelletaan EU:ssa; kansalliset päivämäärät voivat poiketa (ETA:ssa ne seuraavat sopimukseen ottamista). Tarkistettu {d}.",
  pending="Odottaa toimittajan tarkistusta – sisältö voi muuttua.", placeholder="Tätä sivua valmistellaan, ja se odottaa toimittajan tarkistusta. Katso sillä välin sääntelykatsaus toimijahakemistosta.",
  back="← Kuka kukin on", see_map="Toimialakartta", general="Yleiskuvaus", r12_dk="Epäilyttävistä liiketoimista ilmoitetaan Hvidvasksekretariatetille, joka on Tanskan rahanpesun selvittelykeskus (FIU) NSK:n alaisuudessa. Erillistä kryptoverolakia ei ole; Skattestyrelsen soveltaa kryptovaroihin yleisiä verosääntöjä.", r13_fi="Laki 402/2024 täydentää MiCA-asetusta; lain 2 §:n mukaan Finanssivalvonta valvoo säännösten noudattamista.", r14_fi="Epäilyttävistä liiketoimista ilmoitetaan keskusrikospoliisin rahanpesun selvittelykeskukselle (lait 444/2017 ja 445/2017)."),
"is": dict(title="Svona verða reglurnar til", desc="Hvernig rafmyntareglur ESB (MiCA, AMLR, DORA) verða að lögum í Noregi, Svíþjóð, Danmörku, Finnlandi og Íslandi og hver hefur eftirlit með þeim og framfylgir þeim – með heimild fyrir hvert skref.",
  lead="Einfaldað kort af því hvernig rafmyntareglur berast frá Brussel til norrænu ríkjanna fimm og hver hefur eftirlit með þeim og framfylgir þeim. Hver reitur vísar á lagalega heimild sína og, þar sem hún er til, á færsluna í hver er hvað. Veldu land til að fylgja leið þess.",
  s1="ESB-stig", s1p="Framkvæmdastjórn ESB leggur fram tillögu að reglugerð; Evrópuþingið og ráðið samþykkja hana samkvæmt almennri lagasetningarmeðferð. ESMA og EBA útfæra síðan nánari atriði og hafa eftirlit með hluta hennar.",
  s2="Inn í landslög", s2eu="Svíþjóð, Danmörk og Finnland eru aðildarríki ESB: reglugerðir ESB eru bindandi og gilda þar beint. Landslög bæta við því sem reglugerðin lætur hverju ríki eftir, til dæmis hvaða stjórnvald ber ábyrgð.",
  s2eea="Sameiginlega EES-nefndin ákvað 20. febrúar 2025 (ákvörðun nr. 41/2025) að taka MiCA upp í EES-samninginn; Noregur og Ísland innleiddu hana síðan í landslög.",
  s3="Þing og ráðuneyti", s3p="Að jafnaði undirbýr ráðuneytið sem fer með fjármálamarkaði frumvarpið og þjóðþingið samþykkir það.",
  s4="Eftirlit", s4p="Lögbært yfirvald í hverju landi veitir þjónustuveitendum sýndareigna starfsleyfi og hefur eftirlit með þeim.",
  s5="Framfylgd", s5p="Tilkynna skal grunsamleg viðskipti til peningaþvættisskrifstofu (FIU), sem heyrir undir lögreglu eða ákæruvald. Í hverju landi ber skattyfirvald landsins ábyrgð á skattlagningu, einnig á sýndareignum.",
  propose="leggur til", adopt="samþykkir", applies="gildir frá {d}", law="Landslög", parliament="Þing", ministry="Ráðuneyti", supervisor="Eftirlit", fiu="FIU / lögregla", tax="Skattyfirvald",
  act_mica="Markaðir fyrir sýndareignir: starfsleyfi þjónustuveitenda sýndareigna, reglur um útgefendur og stöðugleikamyntir.", act_tfr="„Ferðareglan“: upplýsingar um sendanda og viðtakanda skulu fylgja millifærslum sýndareigna.",
  act_amlr="Reglubók ESB gegn peningaþvætti, einnig fyrir þjónustuveitendur sýndareigna.", act_dora="Stafrænn viðnámsþróttur (UT-áhætta) fjármálafyrirtækja, einnig þjónustuveitenda sýndareigna.",
  ag_esma="Heldur MiCA-skrána og semur tæknilega staðla.", ag_eba="Hefur eftirlit með útgefendum mikilvægra stöðugleikamynta (eignatengdra tákna og rafeyristákna).",
  country="Land", all="Öll", src="heimild", chart="hver er hvað", diagram="Skýringarmynd (allur textinn fylgir hér á eftir)", eea="EES-leiðin", eu_route="ESB-ríki",
  caveat="Einfaldað yfirlit, ekki lögfræðiráðgjöf. Dagsetningar sýna hvenær reglugerð ESB gildir innan ESB; dagsetningar í einstökum ríkjum geta verið aðrar (í EES fylgja þær upptöku í samninginn). Athugað {d}.",
  pending="Bíður yfirferðar ritstjóra – efnið getur breyst.", placeholder="Verið er að undirbúa þessa síðu og hún bíður yfirferðar ritstjóra. Sjá á meðan yfirlit um regluverk í hver er hvað.",
  back="← Hver er hvað", see_map="Yfirlitskort", general="Almenn lýsing", r12_dk="Grunsamleg viðskipti eru tilkynnt til Hvidvasksekretariatet, peningaþvættisskrifstofu Danmerkur (FIU) innan NSK. Engin sérstök skattalög gilda um rafmyntir; Skattestyrelsen beitir almennum skattareglum á sýndareignir.", r13_fi="Lög 402/2024 eru viðbót við MiCA; samkvæmt 2. gr. laganna hefur Finanssivalvonta eftirlit með því að reglunum sé fylgt.", r14_fi="Grunsamleg viðskipti eru tilkynnt til peningaþvættisskrifstofunnar (Rahanpesun selvittelykeskus) innan finnsku rannsóknarlögreglunnar (lög 444/2017 og 445/2017)."),
}
CSS = """<style>
.rules-flow{max-width:760px}
.rflow{display:block;width:100%;max-width:520px;height:auto;margin:6px 0 14px}
.rflow rect{fill:#fff;stroke:var(--ink,#111);stroke-width:1.5}
.rflow text{font:600 13px/1 system-ui,sans-serif;fill:var(--ink,#111)}
.rflow .ar{stroke:var(--accent,#c00);stroke-width:2.5;fill:none;stroke-dasharray:6 6;animation:rdash 1.2s linear infinite}
.rflow .ah{fill:var(--accent,#c00)}
.rflow .eea rect{stroke-dasharray:4 3}
@keyframes rdash{to{stroke-dashoffset:-24}}
@media (prefers-reduced-motion:reduce){.rflow .ar{animation:none;stroke-dasharray:none}.rstep{animation:none!important}}
ol.rsteps{list-style:none;padding:0;margin:0;counter-reset:rs}
.rstep{position:relative;border:1px solid var(--line,#ddd);border-left:4px solid var(--accent,#c00);padding:10px 12px;margin:0 0 22px;background:#fff;animation:rin .5s ease-out both}
.rstep:not(:last-child)::after{content:"";position:absolute;left:24px;bottom:-22px;height:22px;border-left:2px dashed var(--accent,#c00)}
.rstep h2{font-size:17px;margin:0 0 6px}.rstep h2::before{counter-increment:rs;content:counter(rs) ". ";color:var(--accent,#c00)}
@keyframes rin{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.rnodes{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:8px;margin-top:8px}
.rnode{border:1px solid var(--line,#ddd);padding:7px 9px;font-size:13.5px;line-height:1.35}
.rnode b{display:block}.rnode .k{font-size:11.5px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted,#666)}
.rnode .ln{font-size:12px;margin-top:3px}
.rnode[data-route=eea]{border-style:dashed}
.rules-c .seg button[aria-pressed=true]{background:var(--ink,#111);color:#fff}
.rules-hidden{display:none!important}
</style>"""
JS = """<script>(function(){var b=document.querySelectorAll('#rcountry button');function f(c){b.forEach(function(x){x.setAttribute('aria-pressed',x.dataset.c===c?'true':'false')});
document.querySelectorAll('[data-rc]').forEach(function(n){var cs=n.dataset.rc.split(' ');n.classList.toggle('rules-hidden',c!=='all'&&cs.indexOf(c)<0)});
document.querySelectorAll('[data-route-text]').forEach(function(n){var r=n.dataset.routeText;n.classList.toggle('rules-hidden',c!=='all'&&((r==='eea')!==(c==='NO'||c==='IS')))});}
b.forEach(function(x){x.addEventListener('click',function(){f(x.dataset.c);try{history.replaceState(null,'',x.dataset.c==='all'?location.pathname:'#'+x.dataset.c)}catch(e){}})});
var h=(location.hash||'').slice(1).toUpperCase();if(['NO','SE','DK','FI','IS'].indexOf(h)>=0)f(h);})();</script>"""

def load(root):
    try: return json.load(open(os.path.join(root, "rules.json"), encoding="utf-8"))
    except FileNotFoundError: return None

def build(m, ctx):
    R = load(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if not R: return
    L = m.LANG; S = dict(STR["en"], **STR.get(L, {})); E = m.E
    srcs = R["sources"]; ids = {e["id"] for e in ctx["ents"]}
    def s(k, txt=None):
        x = srcs[k]; return f'<a href="{E(x["url"])}" rel="noopener" target="_blank" title="{E(x["title"])}">{E(txt or x["publisher"])}</a>'
    def chart(org):
        return f' · <a href="../org-chart/#{E(org)}">{E(S["chart"])}</a>' if org and org in ids else ""
    def d(iso): return m.i18n.long_date(L, datetime.date.fromisoformat(iso))
    checked = d(R["checked"])
    title = S["title"]
    if R.get("review") == "pending" and not m.PREVIEW:
        body = (f'<h1>{E(title)}</h1><p class="lead">{E(S["placeholder"])}</p>'
                f'<p><a href="../org-chart/">{E(S["back"])}</a> · <a href="../org-chart/#industry-map">{E(S["see_map"])}</a></p>')
        m.page("rules", title, "org-chart", body, S["desc"]); return
    C = R["countries"]; order = [c for c in m.COUNTRY_CODES if c in C]
    def node(kind, name, extra="", rc="", route=""):
        return (f'<div class="rnode"{f" data-rc={chr(34)}{rc}{chr(34)}" if rc else ""}{f" data-route={chr(34)}{route}{chr(34)}" if route else ""}>'
                f'<span class="k">{E(kind)}</span><b>{E(name)}</b>{extra}</div>')
    flagname = lambda c: f'{m.flag(c)} {E(m.cname(c))}'
    # 1. EU
    eu = R["eu"]
    n1 = "".join(node(S["propose"] if i["role"] == "propose" else S["adopt"], i["name"], f'<div class="ln">{s(i["src"])}</div>') for i in eu["institutions"])
    n1 += "".join(node(a["ref"], a["name"], f'<div>{E(S[a["note_key"]])}</div><div class="ln">{E(S["applies"].format(d=d(a["applies"])))} · {s(a["src"])}</div>') for a in eu["acts"])
    n1 += "".join(node("EU", a["name"], f'<div>{E(S[a["note_key"]])}</div><div class="ln">{s(a["src"])}{(" · " + s(a["src2"])) if a.get("src2") else ""}{chart(a.get("org"))}</div>') for a in eu["agencies"])
    # 2. national law
    dec = R["eea"]["decision"]
    n2 = "".join(node(S["law"], C[c]["law"], f'<div class="ln">{flagname(c)} · {E(S["eea"] if C[c]["route"] == "eea" else S["eu_route"])} · {s(C[c]["law_src"])}</div>', rc=c, route=C[c]["route"]) for c in order)
    p2 = (f'<p data-route-text="eu">{E(S["s2eu"])} <span class="meta">({s("mica")})</span></p>'
          f'<p data-route-text="eea">{E(S["s2eea"])} <span class="meta">({s(R["eea"]["src"])})</span></p>')
    # 3. parliament + ministry
    n3 = "".join(node(S["parliament"], C[c]["parliament"], f'<div class="ln">{flagname(c)} · {s(C[c]["law_src"])}{chart(C[c].get("parliament_org"))}</div>', rc=c)
                 + node(S["ministry"], C[c]["ministry"]["name"], f'<div class="ln">{flagname(c)}{chart(C[c]["ministry"]["org"])}</div>', rc=c) for c in order)
    # 4. supervisor
    n4 = "".join(node(S["supervisor"], C[c]["supervisor"]["name"], f'<div class="ln">{flagname(c)} · {s(C[c]["supervisor"]["src"])}{(" · " + s(C[c]["supervisor"]["src2"])) if C[c]["supervisor"].get("src2") else ""}{chart(C[c]["supervisor"]["org"])}</div>', rc=c) for c in order)
    def notes(k):  # country-specific sentences (editor-approved wording), shown with the country filter
        return "".join(f'<p data-rc="{c}">{m.flag(c)} {E(S[C[c][k]])} <span class="meta">({", ".join(s(x) for x in C[c].get(k + "_src", []))})</span></p>' for c in order if C[c].get(k))
    # 5. enforcement
    n5 = "".join(node(S[x["kind"]], x["name"], f'<div class="ln">{flagname(c)}{(" · " + s(x["src"])) if x.get("src") else ""}{(" · " + s(x["src2"])) if x.get("src2") else ""}{chart(x["org"])}</div>', rc=c) for c in order for x in C[c]["enforce"])
    steps = [(S["s1"], f'<p>{E(S["s1p"])}</p>', n1, ""), (S["s2"], p2, n2, ""), (S["s3"], f'<p><span class="tag">{E(S["general"])}</span> {E(S["s3p"])}</p>', n3, ""),
             (S["s4"], f'<p>{E(S["s4p"])}</p>' + notes("note4"), n4, ""), (S["s5"], f'<p>{E(S["s5p"])}</p>' + notes("note5"), n5, "")]
    lis = "".join(f'<li class="rstep" style="animation-delay:{i * 0.12:.2f}s"><h2>{E(h)}</h2>{p}<div class="rnodes">{n}</div></li>' for i, (h, p, n, _) in enumerate(steps))
    # decorative SVG summary (aria-hidden); the list is the text version
    lab = [S["s1"], S["s2"], S["s3"], S["s4"], S["s5"]]
    boxes = "".join(f'<g transform="translate(10,{10 + i * 62})"><rect width="500" height="40" rx="6"/><text x="16" y="25">{i + 1}. {E(t_)}</text></g>' for i, t_ in enumerate(lab))
    arrows = "".join(f'<path class="ar" d="M60 {50 + i * 62} V{70 + i * 62}"/><path class="ah" d="M54 {66 + i * 62} L60 {72 + i * 62} L66 {66 + i * 62}Z"/>' for i in range(4))
    eea = f'<g class="eea" transform="translate(300,{10 + 62 + 4})"><rect width="200" height="32" rx="6"/><text x="12" y="21">NO · IS: {E(S["eea"])}</text></g>'
    svg = f'<svg class="rflow" viewBox="0 0 520 {10 + 5 * 62}" aria-hidden="true" focusable="false">{boxes}{arrows}{eea}</svg>'
    seg = (f'<div class="rules-c"><div class="seg" id="rcountry" role="group" aria-label="{E(S["country"])}"><button type="button" data-c="all" aria-pressed="true">{E(S["all"])}</button>'
           + "".join(f'<button type="button" data-c="{c}" aria-pressed="false">{m.flag(c)} {E(m.cname(c))}</button>' for c in order) + '</div></div>')
    pend = f'<p class="notice"><b>{E(S["pending"])}</b></p>' if R.get("review") == "pending" else ""
    body = (CSS + f'<div class="rules-flow"><h1>{E(title)}</h1>{pend}<p class="lead">{E(S["lead"])}</p>'
            f'<p><a href="../org-chart/">{E(S["back"])}</a> · <a href="../org-chart/#industry-map">{E(S["see_map"])}</a></p>{seg}'
            f'<figure><figcaption class="meta">{E(S["diagram"])}</figcaption>{svg}</figure><ol class="rsteps">{lis}</ol>'
            f'<p class="meta">{E(S["caveat"].format(d=checked))}</p></div>')
    m.page("rules", title, "org-chart", body, S["desc"], extra_script=JS)
    if L == "en": print(f"rules: page built ({'preview, ' if m.PREVIEW else ''}review={R.get('review')}), {len(srcs)} sources")
