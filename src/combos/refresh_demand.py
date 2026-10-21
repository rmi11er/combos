"""Bounded, publication-causal demand tracking for shadow depth verification."""
import json
import zlib


class RefreshDemand:
    def __init__(self, token_by_ticker, window=60):
        self.tokens=dict(token_by_ticker);self.window=window;self.seen={};self.cursor=0

    def poll(self, db, now, limit=2000):
        high=db.execute('SELECT COALESCE(MAX(seq),0) FROM events').fetchone()[0]
        rows=db.execute("SELECT seq,received_at,payload FROM events WHERE seq>? AND seq<=? AND kind='rfq_refresh_demand' ORDER BY seq LIMIT ?",(self.cursor,high,limit)).fetchall()
        for seq,at,raw in rows:
            if at>now or now-at>=self.window:continue
            p=json.loads(zlib.decompress(raw))
            for ticker in p['market_tickers']:
                token=self.tokens.get(ticker)
                if token:self.seen[token]=max(at,self.seen.get(token,float('-inf')))
        self.cursor=rows[-1][0] if len(rows)==limit else high
        self.seen={t:at for t,at in self.seen.items() if 0<=now-at<self.window}
        return dict(self.seen)


def choose(candidates, attempted, demand, now, batch, exploration=20, refresh_after=8):
    """Refresh due demanded books first; preserve oldest-attempted exploration."""
    order=sorted(candidates,key=lambda t:(attempted.get(t,float('-inf')),t))
    due=[t for t in order if t in demand and now-attempted.get(t,float('-inf'))>=refresh_after]
    priority=due[:max(0,batch-min(exploration,batch-1))]
    chosen=set(priority)
    return priority+[t for t in order if t not in chosen][:batch-len(priority)]
