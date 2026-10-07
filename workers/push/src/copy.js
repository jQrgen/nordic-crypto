// Notification chrome. The story title and summary come from the publish payload
// (English, plus summary_i18n when the editor approved a translation).
// A missing language falls back to English. Norwegian says nothing abbreviated as AI or KI.

export const LANGS = [
  "en", "nn", "nb", "sv", "da", "fi", "is",
  "zh", "hi", "es", "fr", "ar", "bn", "pt", "ru", "ur", "id", "de", "ja", "sw", "mr",
];

export const COUNTRIES = ["NO", "SE", "DK", "FI", "IS"];

export const COPY = {
  en: { one: "New story", many: "{n} new stories", more: "and {n} more" },
  nn: { one: "Ny sak", many: "{n} nye saker", more: "og {n} fleire" },
  nb: { one: "Ny sak", many: "{n} nye saker", more: "og {n} til" },
  sv: { one: "Ny artikel", many: "{n} nya artiklar", more: "och {n} till" },
  da: { one: "Ny artikel", many: "{n} nye artikler", more: "og {n} mere" },
  fi: { one: "Uusi juttu", many: "{n} uutta juttua", more: "ja {n} muuta" },
  is: { one: "Ný frétt", many: "{n} nýjar fréttir", more: "og {n} í viðbót" },
  zh: { one: "新报道", many: "{n} 条新报道", more: "另有 {n} 条" },
  hi: { one: "नई ख़बर", many: "{n} नई ख़बरें", more: "और {n}" },
  es: { one: "Noticia nueva", many: "{n} noticias nuevas", more: "y {n} más" },
  fr: { one: "Nouveau sujet", many: "{n} nouveaux sujets", more: "et {n} de plus" },
  ar: { one: "خبر جديد", many: "{n} أخبار جديدة", more: "و{n} أخرى" },
  bn: { one: "নতুন খবর", many: "{n}টি নতুন খবর", more: "আরও {n}টি" },
  pt: { one: "Notícia nova", many: "{n} notícias novas", more: "e mais {n}" },
  ru: { one: "Новая новость", many: "{n} новых новостей", more: "и ещё {n}" },
  ur: { one: "نئی خبر", many: "{n} نئی خبریں", more: "اور {n} مزید" },
  id: { one: "Berita baru", many: "{n} berita baru", more: "dan {n} lagi" },
  de: { one: "Neue Meldung", many: "{n} neue Meldungen", more: "und {n} weitere" },
  ja: { one: "新しい記事", many: "新しい記事 {n} 件", more: "ほか {n} 件" },
  sw: { one: "Habari mpya", many: "Habari mpya {n}", more: "na {n} zaidi" },
  mr: { one: "नवीन बातमी", many: "{n} नवीन बातम्या", more: "आणि आणखी {n}" },
};

export function copyFor(lang) {
  return COPY[lang] || COPY.en;
}
