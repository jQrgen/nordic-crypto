import { Cormorant_Garamond, IBM_Plex_Mono, Schibsted_Grotesk } from "next/font/google";
import { rootSocial } from "@/lib/social";
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

export const metadata = rootSocial();

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable} ${mono.variable}`} suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=new URLSearchParams(location.search).get("theme");if(t==="dark"||t==="light")localStorage.setItem("nc-theme",t);if(localStorage.getItem("nc-theme")==="dark")document.documentElement.setAttribute("data-theme","dark");var m=location.pathname.match(/^\\/(bch|nexa)\\/(block|tx|address|token)\\/([^/]+)\\/?$/);if(m){var key={block:"height",tx:"txid",address:"address",token:"id"}[m[2]];location.replace("/"+m[1]+"/"+m[2]+"/?"+key+"="+encodeURIComponent(decodeURIComponent(m[3])))}}catch(e){}`,
          }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
