/**
 * Links from the nordiccrypto.no front page, in the order a reader meets them.
 * Header (build.header_buttons): Follow, Telegram, X, source code.
 * Signup is off (newsletter/config.json), so the gold button says Follow and
 * opens /newsletter/#signup, the same as header_subscribe_button.
 * Footer follow column, after those: RSS, then the TestFlight invite with the
 * Apple TV note. Labels and titles are the English strings in i18n/en.py.
 */
export type SiteIcon = "telegram" | "x" | "github" | "rss";

export type SiteLink = {
  id: string;
  href: string;
  label: string;
  title?: string;
  note?: string;
  icon?: SiteIcon;
  variant: "gold" | "icon" | "text";
};

export const siteLinks: readonly SiteLink[] = [
  {
    id: "follow",
    href: "https://nordiccrypto.no/newsletter/#signup",
    label: "Follow",
    variant: "gold",
  },
  {
    id: "telegram",
    href: "https://t.me/nordiccryptochat",
    label: "Join on Telegram",
    title: "Nordic Crypto on Telegram (t.me/nordiccryptochat), the brand chat",
    icon: "telegram",
    variant: "icon",
  },
  {
    id: "x",
    href: "https://x.com/nordiccryptobot",
    label: "Follow on X",
    title: "Nordic Crypto on X (@nordiccryptobot), the site's own account",
    icon: "x",
    variant: "icon",
  },
  {
    id: "github",
    href: "https://github.com/jQrgen/nordic-crypto",
    label: "Source code",
    title: "Source code",
    icon: "github",
    variant: "icon",
  },
  {
    id: "rss",
    href: "https://nordiccrypto.no/rss.xml",
    label: "RSS",
    title: "RSS feed",
    icon: "rss",
    variant: "icon",
  },
  {
    id: "ios",
    href: "https://testflight.apple.com/join/nQ2fpjZn",
    label: "Get the iOS app (TestFlight)",
    note: "Especially supports Apple TV.",
    variant: "text",
  },
];

/** The news site. The explorer header links back here. */
export const newsSite = {
  href: "https://nordiccrypto.no/",
  label: "nordiccrypto.no",
} as const;
