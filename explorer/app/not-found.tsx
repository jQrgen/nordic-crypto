import { Frame } from "@/components/frame";
import { Missing } from "@/components/states";

export default function NotFound() {
  return (
    <Frame chain="nexa">
      <Missing q="" chainId="nexa" page />
    </Frame>
  );
}
