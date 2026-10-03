#!/usr/bin/env python3
"""One-off seed for data/academia.json (own research, 3 Oct 2026). Every row: status "awaiting editor".
Courses/groups/research rows were checked against their own pages on the check date. Publication metadata is
fetched from OpenAlex by DOI (nothing typed by hand) and every DOI is verified to resolve via the doi.org handle API.
Norwegian rows mirror Kryptonytt's Akademia seed, written in English. Re-run: .venv/bin/python tools/seed_academia.py"""
import json, os, sys, time, requests
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "NordicCrypto/0.1 (local preview; https://jqrgen.github.io/nordic-crypto/)"}
C = "2026-10-03"; ST = "awaiting editor"
# (country, code, name, institution, level, url, about)
courses = [
 ("NO", "TTM4195", "Blockchain Technologies and Cryptographic Tools", "NTNU", "Master's, 7.5 ECTS, autumn", "https://www.ntnu.no/studier/emner/TTM4195", "The cryptography behind Bitcoin and other cryptocurrencies, cryptocurrency design and smart contracts."),
 ("NO", "IN5420", "Distributed Blockchain Technologies", "University of Oslo", "Master's, 10 ECTS, spring", "https://www.uio.no/studier/emner/matnat/ifi/IN5420/", "Research seminar on Bitcoin, blockchain storage, consensus protocols, security and privacy."),
 ("NO", "IN9420", "Distributed Blockchain Technologies", "University of Oslo", "PhD, 10 ECTS, spring", "https://www.uio.no/studier/emner/matnat/ifi/IN9420/index.html", "PhD version of IN5420."),
 ("NO", "INFO384", "Blockchain Technology and Formal Methods", "University of Bergen", "Master's, 15 ECTS", "https://www4.uib.no/studier/emner/info384", "Blockchain theory, consensus (PoW/PoS) analysed with formal methods, smart contracts in Solidity."),
 ("NO", "INFO384B", "Blockchain Technology", "University of Bergen", "Master's, 10 ECTS, autumn", "https://www4.uib.no/studier/emner/info384b", "Blockchain theory and models, consensus, Ethereum smart contracts and cryptography."),
 ("NO", "IKT519", "Blockchain and Distributed Ledger Technology", "University of Agder", "Master's, 7.5 ECTS, spring", "https://www.uia.no/english/studies/courses/2026/spring/ikt519.html", "Cryptography in blockchains, Bitcoin consensus, script, mining and anonymity, altcoins."),
 ("NO", "FOR20", "Introduction to Blockchain", "NHH Norwegian School of Economics", "Bachelor's", "https://www.nhh.no/en/courses/introduction-to-blockchain/", "What a blockchain is, consensus protocols, smart contracts, digitalisation of assets and DeFi."),
 ("NO", "LUS2030", "Blockchains, Cryptocurrency and Central Bank Digital Currency", "BI Norwegian Business School", "Continuing education (module)", "https://www.bi.no/studier-og-kurs/videreutdanning/kompetanseheving-bransjeprogram/digital-transformasjon-i-finansnaringen/", "Bitcoin and blockchain technology, other cryptocurrencies, central bank digital currency, DeFi, NFTs and Web3."),
 ("SE", "DD2585", "Programmable Society with Blockchains and Smart Contracts", "KTH Royal Institute of Technology", "Master's, 7.5 credits", "https://www.kth.se/student/kurser/kurs/DD2585?l=en", "Distributed ledger technology and blockchains, running blockchain protocols and nodes, smart-contract programming and engineering; project-based."),
 ("SE", "FID3022", "Blockchain Fundamentals: Technology and Applications", "KTH Royal Institute of Technology", "PhD, 7.5 credits", "https://www.kth.se/student/kurser/kurs/FID3022", "Survey course building Bitcoin from the bottom up: cryptography, game theory, economics, earlier digital currencies and blockchain applications."),
 ("SE", "JAEN60", "Smart Contracts, Blockchain and FinTech", "Lund University (Faculty of Law)", "Master's, 7.5 credits", "https://kursplaner.lu.se/pdf/kurs/en/JAEN60", "Legal implications of blockchain and distributed ledgers, with a focus on Bitcoin, smart contracts and other financial use cases."),
 ("FI", "COMM.NET.500", "P2P Systems and Blockchain Technologies", "Tampere University", "5 ECTS (also via FITech)", "https://opiskelijanopas.tuni.fi/en/tampere-university/curriculum/course-units/tut-cu-g-45503?year=2026", "Peer-to-peer systems and DHTs, then blockchain concepts, cryptocurrencies, Bitcoin in detail, smart contracts, proof of work and proof of stake."),
 ("FI", "CS-AJ0100", "FITech 101: Blockchain Business Applications", "Aalto University (open university, FITech)", "Basic, 1 ECTS, online", "https://www.aalto.fi/en/open-university-course-list/fitech-101-blockchain-business-applications", "Introductory, non-coding course on blockchain business models: NFTs, ICOs, security tokens, smart contracts and private DLT. The 2025–26 run ended 16 July 2026."),
 ("IS", "T-714-FINT", "Financial Technologies and Applications", "Reykjavík University", "Master's, 6 ECTS", "https://www.ru.is/en/research-center/ru-fintech", "FinTech course with a special focus on blockchain: distributed ledgers, consensus, trust, smart contracts and Hyperledger; project work with RU FinTech partners."),
 ("IS", "STÆ532M", "Cryptocurrencies (Rafmyntir)", "University of Iceland", "Undergraduate/graduate, 6 ECTS, autumn", "https://ugla.hi.is/kennsluskra/index.php?tab=nam&chapter=namskeid&id=70953120216", "Wallets, transactions, blocks and chains, mining algorithms, exchanges and atomic swaps, using the Smileycoin cryptocurrency. Course page found is the 2021–22 catalogue; current offering not confirmed."),
]
# (country, name, institution, active?, activity note, about, url)
groups = [
 ("NO", "BISO Web3 Society", "BI Norwegian Business School (BISO Oslo)", False, "Latest dated activity found: guest lectures and an event with Kaupr in November 2024 (more than 12 months ago).", "Student society for Web3 and crypto at BI.", "https://www.kaupr.io/en/news/the-web3-society-at-bi-is-ramping-up-its-activities"),
 ("NO", "Blockwave Norway", "University of Oslo (student initiative)", False, "Covered by Titan.uio.no in May 2019. No newer dated activity found.", "Blockchain student organisation started by a UiO student.", "https://www.titan.uio.no/utdanning/2019/blockchain-er-faget-der-studentene-er-laerere.html"),
 ("FI", "Aalto Bitcoin", "Aalto University (student organisation)", True, "Dated activity: co-hosted “Slush Dagen Efter” with BTCHEL; announced on LinkedIn on 4 Nov 2025 (within the last 12 months).", "Student organisation raising awareness of Bitcoin and the blockchain industry among Finnish students.", "https://www.linkedin.com/posts/aalto-bitcoin_slush-dagen-efter-by-btchel-x-aalto-bitcoin-activity-7391540339528048640-LVFb"),
 ("SE", "KTH Blockchain Initiative", "KTH Royal Institute of Technology (student initiative)", False, "Website is up but lists no dated events; no dated activity in the last 12 months found.", "Student initiative connecting KTH students with blockchain and Web3 talks, meetups and industry.", "https://kthbci.org/"),
 ("SE", "Bitcoinstudenter Stockholm (formerly Kryptostudenter Stockholm)", "Stockholm University (student association)", False, "Latest dated activity found: name change announced in October 2024 (more than 12 months ago).", "Student association at Stockholm University about Bitcoin and crypto.", "https://linkedin.com/company/kryptostudenter-stockholm"),
]
# (country, name, institution, about, url)
research = [
 ("NO", "Blockchain-UiO", "University of Oslo, Department of Informatics", "Academic–industry lab for blockchain technology: research, courses, master's theses and industry collaboration.", "https://www.mn.uio.no/ifi/english/research/networks/blockchainlab/index.html"),
 ("NO", "Decentralised Systems Engineering Lab", "NTNU, Department of Computer Science", "Research on privacy and anonymity in cryptocurrencies, cryptocurrency analysis for law enforcement, consensus, DeFi and Lightning.", "https://www.ntnu.edu/idi/dse"),
 ("NO", "Trust and Transparency in Digital Society Through Blockchain Technology", "NTNU Digital Transformation", "Interdisciplinary project with six sub-projects: cryptography, networks, identity, value chains, health and organisation.", "https://www.ntnu.edu/digital-transformation/blockchain"),
 ("SE", "Blockchain Lab (BLAB)", "University of Gothenburg, Swedish Center for Digital Innovation", "Research and learning environment for blockchain solutions; courses, experiments and industry collaboration.", "https://www.scdi.se/blockchain/"),
 ("SE", "Yggdrasil: Network Security for Blockchain and Decentralized Systems", "Chalmers University of Technology (research project, 2026–)", "Network-layer security of blockchains: gossip and block propagation, attacks on consensus, deanonymisation and cross-chain bridges.", "https://research.chalmers.se/en/project/12829"),
 ("FI", "OnchainApp – Exploring Onchain Data", "University of Oulu, INTERACT Research Group", "Project on collecting and analysing public on-chain data beyond DeFi.", "https://interact.oulu.fi/onchainapp"),
 ("IS", "RU FinTech", "Reykjavík University", "Research centre whose themes include blockchain, cryptocurrencies and regulation; partners include Íslandsbanki.", "https://www.ru.is/en/research-center/ru-fintech"),
]
dois = {"NO": ["10.1016/j.giq.2017.09.007", "10.1016/j.frl.2018.08.010", "10.1016/j.jebo.2020.05.005", "10.1007/s11187-019-00286-y",
               "10.1016/j.ijforecast.2018.09.005", "10.1016/j.frl.2021.102031", "10.1016/j.frl.2016.09.025"],
        "SE": ["10.1109/access.2019.2936094", "10.1016/j.bushor.2019.01.009", "10.1016/j.tele.2018.10.004", "10.1016/j.jsis.2018.10.002", "10.1016/j.frl.2022.102696"],
        "FI": ["10.1007/s12599-017-0505-1", "10.1016/j.jnca.2020.102857", "10.1016/j.resourpol.2020.101816", "10.1016/j.techfore.2021.120649", "10.1016/j.cie.2019.07.023"],
        "IS": ["10.1016/j.ribaf.2021.101546", "10.1016/j.frl.2022.103131", "10.1016/j.infsof.2021.106762", "10.1016/j.physa.2021.126484"]}
def doi_ok(d):
    r = requests.get(f"https://doi.org/api/handles/{d}", headers=UA, timeout=30)
    return r.status_code == 200 and r.json().get("responseCode") == 1
pubs, bad = [], []
for c, ds in dois.items():
    for d in ds:
        if not doi_ok(d): bad.append(d); continue
        w = requests.get(f"https://api.openalex.org/works/doi:{d}", headers=UA, timeout=30).json()
        inst = []
        for a in w["authorships"]:
            for i in a["institutions"]:
                if i.get("country_code") == c and i["display_name"] not in inst: inst.append(i["display_name"])
        pubs.append({"country": c, "title": w["title"], "authors": [a["author"]["display_name"] for a in w["authorships"]], "institution": ", ".join(inst),
                     "year": w["publication_year"], "venue": ((w.get("primary_location") or {}).get("source") or {}).get("display_name"),
                     "doi": d, "url": f"https://doi.org/{d}", "db": w["id"], "db_name": "OpenAlex", "source": f"https://doi.org/{d}", "checked": C, "status": ST, "origin": "seed"})
        time.sleep(0.3)
if bad: print("DOIs that did not resolve (dropped):", bad, file=sys.stderr)
out = {"updated": C, "note": "Seed from own research; awaiting editor. Rows become public only when approved in queue/approved.json (academia.approve).",
 "rules": ["A course is listed only when blockchain or crypto is a substantial part of the syllabus on its own course page.",
           "Every DOI link is checked against doi.org before it is listed.",
           "A student group is marked active only with dated activity in the last 12 months; otherwise inactive.",
           "Every row carries a source, a check date and a status."],
 "courses": [{"country": a, "code": b, "name": c, "institution": d, "level": e, "url": f, "about": g, "source": f, "checked": C, "status": ST, "origin": "seed"} for a, b, c, d, e, f, g in courses],
 "groups": [{"country": a, "name": b, "institution": c, "active": d, "activity": e, "about": f, "url": g, "source": g, "checked": C, "status": ST, "origin": "seed"} for a, b, c, d, e, f, g in groups],
 "publications": pubs,
 "research": [{"country": a, "name": b, "institution": c, "about": d, "url": e, "source": e, "checked": C, "status": ST, "origin": "seed"} for a, b, c, d, e in research]}
json.dump(out, open(os.path.join(ROOT, "data", "academia.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print({k: len(v) for k, v in out.items() if isinstance(v, list) and k != "rules"}, "bad DOIs:", bad)
