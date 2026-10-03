#!/usr/bin/env bash
# Checks that validate() in src/worker.js gives exactly the same result as tipserver/server.py validate() for tests/parity_cases.json.
set -euo pipefail
cd "$(dirname "$0")"; source ./env.sh
js=$(node --input-type=module -e '
import { validate } from "./src/worker.js"; import fs from "fs";
const c = JSON.parse(fs.readFileSync("tests/parity_cases.json"));
c.push({url:"https://e24.no",note:"é".repeat(1000)},{url:"https://e24.no",note:"😀".repeat(1000)},{url:"https://e24.no",note:"x".repeat(1001)},{url:"https://e24.no",name:"n".repeat(101)});
console.log(JSON.stringify({c, r: c.map(validate)}));')
JS="$js" python3 -c '
import json,os,sys; sys.path.insert(0,"../tipserver"); sys.argv=["x"]; import server
d=json.loads(os.environ["JS"]); bad=0
for a,r in zip(d["c"],d["r"]):
    p=list(server.validate(a))
    if p!=r: bad+=1; print("DIFF", json.dumps(a)[:80], "py", p, "js", r)
n=len(d["c"]); print(f"parity: {n-bad}/{n} cases identical"); sys.exit(1 if bad else 0)'
