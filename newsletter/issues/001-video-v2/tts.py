import asyncio, json, sys, edge_tts
sys.path.insert(0, '.'); import content as C
B = 'build/'
async def main():
    names = sys.argv[1:] or list(C.VO)
    for n in names:
        t = C.VO[n]
        for attempt in range(3):
            try:
                c = edge_tts.Communicate(t, C.VOICE, rate=C.RATE, boundary="SentenceBoundary"); bounds = []
                with open(B + n + '.mp3', 'wb') as f:
                    async for ch in c.stream():
                        if ch['type'] == 'audio': f.write(ch['data'])
                        elif ch['type'].endswith('Boundary'): bounds.append((ch['offset']/1e7, (ch['offset']+ch['duration'])/1e7, ch['text']))
                json.dump(bounds, open(B + n + '.json', 'w')); print(n, len(bounds), flush=True); break
            except Exception as e: print('retry', n, e)
asyncio.run(main())
