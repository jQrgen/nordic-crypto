// Short pages the Worker returns for a normal form POST (no site JavaScript).
// Nordic languages are written out. Every other site language uses English.
// Norwegian must say «kunstig intelligens», never «AI» or «KI».

export const COPY = {
  en: {
    title: "Tip received",
    thanks: "Thank you. Your tip is in the private inbox. It is not public. The editorial team will read it, including human editors and an editor that is artificial intelligence. The artificial intelligence is not a human. We do not reply to every tip, and a tip is not a promise of publication.",
    fail: "The tip could not be sent. Nothing was published.",
    back: "Back to the tip page",
  },
  nn: {
    title: "Tips motteke",
    thanks: "Takk. Tipset ditt ligg i den private innboksen. Det er ikkje offentleg. Redaksjonen vil lese det, medrekna menneskelege redaktørar og ein redaktør som er kunstig intelligens. Den kunstige intelligensen er ikkje eit menneske. Vi svarar ikkje på kvart tips, og eit tips er ikkje eit løfte om publisering.",
    fail: "Tipset kunne ikkje sendast. Ingenting blei publisert.",
    back: "Tilbake til tipssida",
  },
  nb: {
    title: "Tips mottatt",
    thanks: "Takk. Tipset ditt ligger i den private innboksen. Det er ikke offentlig. Redaksjonen vil lese det, inkludert menneskelige redaktører og en redaktør som er kunstig intelligens. Den kunstige intelligensen er ikke et menneske. Vi svarer ikke på hvert tips, og et tips er ikke et løfte om publisering.",
    fail: "Tipset kunne ikke sendes. Ingenting ble publisert.",
    back: "Tilbake til tipssiden",
  },
  sv: {
    title: "Tipset mottaget",
    thanks: "Tack. Ditt tips ligger i den privata inkorgen. Det är inte offentligt. Redaktionen kommer att läsa det, inklusive mänskliga redaktörer och en redaktör som är artificiell intelligens. Den artificiella intelligensen är inte en människa. Vi svarar inte på varje tips, och ett tips är inte ett löfte om publicering.",
    fail: "Tipset kunde inte skickas. Ingenting publicerades.",
    back: "Tillbaka till tipssidan",
  },
  da: {
    title: "Tip modtaget",
    thanks: "Tak. Dit tip ligger i den private indbakke. Det er ikke offentligt. Redaktionen læser det, herunder menneskelige redaktører og en redaktør, der er kunstig intelligens. Den kunstige intelligens er ikke et menneske. Vi svarer ikke på hvert tip, og et tip er ikke et løfte om offentliggørelse.",
    fail: "Tippet kunne ikke sendes. Intet blev offentliggjort.",
    back: "Tilbage til tipsiden",
  },
  fi: {
    title: "Vinkki vastaanotettu",
    thanks: "Kiitos. Vinkkisi on yksityisessä laatikossa. Se ei ole julkinen. Toimitus lukee sen. Toimitukseen kuuluu ihmistoimittajia ja toimittaja, joka on tekoäly. Tekoäly ei ole ihminen. Emme vastaa jokaiseen vinkkiin, eikä vinkki ole lupaus julkaisusta.",
    fail: "Vinkkiä ei voitu lähettää. Mitään ei julkaistu.",
    back: "Takaisin vinkkisivulle",
  },
  is: {
    title: "Ábending móttekin",
    thanks: "Takk. Ábendingin þín er í einkainnhólfinu. Hún er ekki opinber. Ritstjórnin les hana, þar á meðal mannlegir ritstjórar og ritstjóri sem er gervigreind. Gervigreindin er ekki manneskja. Við svörum ekki hverri ábendingu, og ábending er ekki loforð um birtingu.",
    fail: "Ekki tókst að senda ábendinguna. Ekkert var birt.",
    back: "Til baka á ábendingasíðuna",
  },
};

export function strings(lang) {
  const k = String(lang || "").toLowerCase();
  return COPY[k] || COPY.en;
}
