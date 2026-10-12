import type { Metadata } from "next";
import { Suspense } from "react";
import { SearchView } from "./search-view";

export const metadata: Metadata = { title: "Search" };

// Static export: the query is read in the browser, not on a server.
export default function SearchPage() {
  return (
    <Suspense fallback={null}>
      <SearchView />
    </Suspense>
  );
}
