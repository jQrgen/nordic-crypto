"use client";

import { Frame } from "@/components/frame";
import { Fault } from "@/components/states";
import { defaultChain } from "@/lib/data";

export default function Error() {
  return (
    <Frame chain={defaultChain}>
      <Fault />
    </Frame>
  );
}
