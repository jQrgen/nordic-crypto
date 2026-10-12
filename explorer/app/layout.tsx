import type { Metadata } from "next";
import { Cormorant_Garamond, IBM_Plex_Mono, Schibsted_Grotesk } from "next/font/google";
import "./globals.css";

const display = Cormorant_Garamond({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-display",
});

const sans = Schibsted_Grotesk({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-ui",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: {
    default: "Nordic Crypto Explorer",
    template: "%s · Nordic Crypto Explorer",
  },
  description: "Design prototype of a Bitcoin Cash and Nexa explorer for explorer.nordiccrypto.no.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable} ${mono.variable}`} suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=new URLSearchParams(location.search).get("theme");if(t==="dark"||t==="light")localStorage.setItem("nc-theme",t);if(localStorage.getItem("nc-theme")==="dark")document.documentElement.setAttribute("data-theme","dark")}catch(e){}`,
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
