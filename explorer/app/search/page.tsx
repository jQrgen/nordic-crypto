import { Suspense } from "react";
import { socialMetadata, socialTitle } from "@/lib/social";
import { SearchView } from "./search-view";

export const metadata = socialMetadata({
  title: socialTitle("Search"),
  description: "Look up a block, transaction, address or token on Bitcoin Cash and Nexa.",
  path: "/search/",
});

// Static export: the query is read in the browser, not on a server.
export default function SearchPage() {
  return (
    <Suspense fallback={null}>
      <SearchView />
    </Suspense>
  );
}
