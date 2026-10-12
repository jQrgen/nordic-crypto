"use client";

import { Frame } from "@/components/frame";
import { Fault } from "@/components/states";

export default function Error() {
  return (
    <Frame chain="nexa">
      <Fault />
    </Frame>
  );
}
