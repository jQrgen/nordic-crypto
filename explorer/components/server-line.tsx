export function ServerLine({
  label,
  version,
  fallback,
  apiHref,
  apiLabel = "API status",
}: {
  label: string;
  version?: string;
  fallback?: boolean;
  apiHref: string;
  apiLabel?: string;
}) {
  return (
    <p className="serverline">
      Read from {label}
      {fallback ? " · fallback" : ""}
      {version ? ` · ${version}` : ""}
      {" · "}
      <a href={apiHref}>{apiLabel}</a>
    </p>
  );
}
