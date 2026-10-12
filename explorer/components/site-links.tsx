import { newsSite, siteLinks, type SiteIcon } from "@/lib/site-links";

const ICONS: Record<SiteIcon, { d: string; size: number }> = {
  telegram: {
    size: 18,
    d: "M21.9 4.3 18.7 19.4c-.2 1.1-.9 1.3-1.8.8l-4.9-3.6-2.4 2.3c-.3.3-.5.5-1 .5l.4-5 9.1-8.2c.4-.4-.1-.6-.6-.2L6.2 13 1.4 11.5c-1-.3-1.1-1 .2-1.5L20.5 2.8c.9-.3 1.7.2 1.4 1.5z",
  },
  x: {
    size: 16,
    d: "M18.2 2.3h3.4l-7.4 8.4 8.7 11.5h-6.8l-5.3-7-6.1 7H1.3l7.9-9L.8 2.3h7l4.8 6.4zm-1.2 17.9h1.9L6.9 4.2H4.9z",
  },
  github: {
    size: 18,
    d: "M12 .5a11.5 11.5 0 0 0-3.64 22.41c.58.1.79-.25.79-.56v-2c-3.2.7-3.88-1.37-3.88-1.37-.52-1.33-1.28-1.69-1.28-1.69-1.04-.71.08-.7.08-.7 1.15.08 1.76 1.19 1.76 1.19 1.03 1.76 2.69 1.25 3.35.96.1-.75.4-1.25.73-1.54-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.29 1.19-3.1-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.17 1.18a11 11 0 0 1 5.77 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.81 1.19 1.84 1.19 3.1 0 4.42-2.69 5.39-5.25 5.68.41.36.78 1.06.78 2.14v3.17c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .5z",
  },
  rss: {
    size: 16,
    d: "M4 4.5v3a12.5 12.5 0 0 1 12.5 12.5h3A15.5 15.5 0 0 0 4 4.5zm0 6v3a6.5 6.5 0 0 1 6.5 6.5h3A9.5 9.5 0 0 0 4 10.5zM6.2 15.6a2.2 2.2 0 1 0 0 4.4 2.2 2.2 0 0 0 0-4.4z",
  },
};

function Icon({ name }: { name: SiteIcon }) {
  const icon = ICONS[name];
  return (
    <svg className="ico" viewBox="0 0 24 24" width={icon.size} height={icon.size} aria-hidden="true" focusable="false">
      <path fill="currentColor" d={icon.d} />
    </svg>
  );
}

/** Front-page social links, then a link back to the news site. Sits at the top of the explorer header. */
export function SiteLinks() {
  return (
    <nav className="socialbar" aria-label="Nordic Crypto on social media">
      {siteLinks.map((link) => {
        if (link.variant === "text") {
          return (
            <span className="app" key={link.id}>
              <a className="soc text" href={link.href} rel="noopener">
                {link.label}
              </a>
              {link.note ? <span className="tvnote">{link.note}</span> : null}
            </span>
          );
        }
        return (
          <a
            key={link.id}
            className={link.variant === "gold" ? "hdrsub" : "soc"}
            href={link.href}
            rel="noopener"
            title={link.title}
          >
            {link.icon ? <Icon name={link.icon} /> : null}
            <span className={link.variant === "icon" ? "lbl" : undefined}>{link.label}</span>
          </a>
        );
      })}
      <a className="soc text back" href={newsSite.href} rel="noopener">
        {newsSite.label}
      </a>
    </nav>
  );
}
