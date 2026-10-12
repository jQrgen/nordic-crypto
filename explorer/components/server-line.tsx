export function ServerLine({
  label,
  version,
  fallback,
  apiHref,
}: {
  label: string;
  version?: string;
  fallback?: boolean;
  apiHref: string;
}) {
  return (
    <p className="serverline">
      Read from {label}
      {fallback ? " · fallback" : ""}
      {version ? ` · ${version}` : ""}
      {" · "}
      <a href={apiHref}>API status</a>
    </p>
  );
}
