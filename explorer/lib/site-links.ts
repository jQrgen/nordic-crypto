/** The explorer's source, a folder in the site repo. */
export const sourceHref = "https://github.com/nordic-crypto-org/nordic-crypto/tree/main/explorer";

/**
 * Links from the nordiccrypto.no front page, in the order a reader meets them.
 * The explorer shows them in its footer.
 * Front page header (build.header_buttons): Follow, Telegram, X, Facebook, YouTube, source code.
 * Signup is off (newsletter/config.json), so the gold button says Follow and
 * opens /newsletter/#signup, the same as header_subscribe_button.
 * Footer follow column, after those: RSS.
 * Labels and titles are the English strings in i18n/en.py.
 */
export type SiteIcon = "telegram" | "x" | "facebook" | "youtube" | "github" | "rss";

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
    id: "facebook",
    href: "https://www.facebook.com/profile.php?id=61595548315551",
    label: "Follow on Facebook",
    title: "Nordic Crypto on Facebook, the brand Page",
    icon: "facebook",
    variant: "icon",
  },
  {
    id: "youtube",
    href: "https://www.youtube.com/@NordicCryptoTV",
    label: "Watch on YouTube",
    title: "Nordic Crypto on YouTube (@NordicCryptoTV), the brand channel",
    icon: "youtube",
    variant: "icon",
  },
  {
    id: "github",
    href: sourceHref,
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
];

/** The news site. The explorer footer links back here. */
export const newsSite = {
  href: "https://nordiccrypto.no/",
  label: "nordiccrypto.no",
} as const;
