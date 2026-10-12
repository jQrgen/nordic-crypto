import type { Metadata } from "next";
import { chains, defaultChain } from "./data";

/** Public origin of the static export. Social crawlers only accept absolute https URLs. */
export const SITE_ORIGIN = "https://explorer.nordiccrypto.no";
export const SITE_NAME = "Nordic Crypto";
export const TWITTER_SITE = "@nordiccryptobot";

/** Share image in public/, copied to the export root. */
export const OG_IMAGE_PATH = "/og.png";
export const OG_IMAGE_URL = `${SITE_ORIGIN}${OG_IMAGE_PATH}`;
export const OG_IMAGE_ALT = "Nordic Crypto Explorer. Bitcoin Cash and Nexa.";
export const OG_IMAGE_WIDTH = 1200;
export const OG_IMAGE_HEIGHT = 630;

const DASH = "\u2013";

export function chainExplorerTitle(name: string) {
  return `${name} explorer ${DASH} ${SITE_NAME}`;
}

export function socialTitle(label: string) {
  return `${label} ${DASH} ${SITE_NAME}`;
}

export function onExplorer(chainName: string, what: string) {
  return `${what} on the ${chainName} explorer.`;
}

export function pageUrl(path: string) {
  return new URL(path, SITE_ORIGIN).href;
}

/**
 * Document title plus a complete Open Graph and Twitter card.
 * A page that sets `openGraph` or `twitter` replaces the layout card, so every
 * page passes the whole card through here instead of a title on its own.
 */
export function socialMetadata({
  title,
  description,
  path,
}: {
  title: string;
  description: string;
  path: string;
}): Metadata {
  const image = {
    url: OG_IMAGE_URL,
    width: OG_IMAGE_WIDTH,
    height: OG_IMAGE_HEIGHT,
    alt: OG_IMAGE_ALT,
  };
  return {
    metadataBase: new URL(SITE_ORIGIN),
    title: { absolute: title },
    description,
    openGraph: {
      title: { absolute: title },
      description,
      url: pageUrl(path),
      siteName: SITE_NAME,
      type: "website",
      images: [image],
    },
    twitter: {
      card: "summary_large_image",
      site: TWITTER_SITE,
      title: { absolute: title },
      description,
      images: [OG_IMAGE_URL],
    },
  };
}

/**
 * Card for the export root. nginx answers `/` with a 302 to the default chain.
 * The root index.html carries that chain's card for crawlers that do not follow.
 */
export function rootSocial(): Metadata {
  const home = chains[defaultChain];
  return socialMetadata({
    title: chainExplorerTitle(home.name),
    description: home.about,
    path: "/",
  });
}
