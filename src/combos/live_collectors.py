"""Read-only WebSocket collection; raw frames and normalized books share a log."""
import asyncio
import json
import time
import uuid
from contextlib import asynccontextmanager
from websockets.asyncio.client import connect
from .event_store import EventStore
from .live_books import Books
from .shadow import auth_headers,WS_URL
from .runtime_clock import Deadline
from .rfq_scope import collection_candidate
from .feed_liveness import FeedLiveness
from .quiet_book_probe import QuietBookProbe,SnapshotRecoveryExhausted,BookResyncRequired
from .snapshot_refresh import SnapshotRefresh
from .refresh_demand import RefreshDemand


@asynccontextmanager
async def flushing_connection(connection, flush):
    """Publish received frames before awaiting the WebSocket close handshake."""
    async with connection as socket:
        try:
            yield socket
        finally:
            flush()


async def collect(path,config,venue,seconds):
    if seconds<=0:raise ValueError('positive duration required')
    # Observation-only mappings (such as player props) are subscribed to and
    # persisted, but are not available to the pricing worker.
    mappings=config['mappings'] + config.get('observation_only_mappings', [])
    probe_config=config.get('polymarket_snapshot_verification')
    probe=QuietBookProbe(probe_config,config.get('mode')) if venue=='polymarket' and probe_config else None
    refresh_config=config.get('kalshi_snapshot_refresh')
    refresh=SnapshotRefresh(refresh_config,config.get('mode')) if venue=='kalshi' and refresh_config else None
    market_tokens={m['market_key']:m.get('polymarket_yes_token') for m in mappings}
    tokens=[m['polymarket_yes_token'] for m in mappings if m.get('polymarket_yes_token')]
    if venue=='polymarket' and not tokens:raise ValueError('no reviewed Polymarket tokens configured')
    store=EventStore(path);run=uuid.uuid4().hex;counter=0;frame_counter=0;pending=[]
    last_flush=time.monotonic();deadline=Deadline(seconds)
    demand=RefreshDemand({m['kalshi_ticker']:m.get('polymarket_yes_token') for m in mappings}) if probe and probe.demand_priority else None
    last_demand_poll=float('-inf')
    def emit(kind,payload,at=None):
        nonlocal counter
        counter+=1;key=f'{venue}:{run}:{counter}'
        pending.append((kind,payload,key,time.time() if at is None else at));return key
    def flush():
        nonlocal last_flush
        if pending:
            with store.transaction():
                for kind,payload,key,at in pending:store.append(kind,venue,payload,key,at)
            pending.clear()
        last_flush=time.monotonic()
    retry=1
    try:
        async with asyncio.timeout(seconds):
            while not deadline.expired():
                books=Books(venue,mappings);session=uuid.uuid4().hex
                if probe:probe.reset(session)
                if refresh:refresh.reset()
                emit('venue_reset',{'venue':venue,'reason':'connect_attempt','session_id':session});flush()
                kwargs={'additional_headers':auth_headers()} if venue=='kalshi' else {}
                url=WS_URL if venue=='kalshi' else 'wss://ws-subscriptions-clob.polymarket.com/ws/market'
                try:
                    async with flushing_connection(connect(url,open_timeout=15,close_timeout=2,max_size=16*1024*1024,ping_interval=20,**kwargs),flush) as ws:
                        liveness=FeedLiveness(time.monotonic())
                        emit('feed_status',{'venue':venue,'status':'connected','session_id':session})
                        static=set(books.maps);requested=set(static);recent={};recent_legs={};book_sid=None;subscription_sent=False;command=1
                        if venue=='kalshi':books.set_targets(static)
                        async def send(payload):
                            emit('subscription_command',payload)
                            await ws.send(json.dumps(payload))
                        if venue=='kalshi':
                            await send({'id':command,'cmd':'subscribe','params':{'channels':['communications','trade','multivariate_market_lifecycle']}})
                            if static:
                                command+=1;subscription_sent=True
                                await send({'id':command,'cmd':'subscribe','params':{'channels':['orderbook_delta'],'market_tickers':sorted(static)}})
                        else:await send({'assets_ids':tokens,'type':'market','custom_feature_enabled':True})
                        last_heartbeat=time.monotonic();last_ping=time.monotonic();last_subscription=time.monotonic();retry=1
                        while True:
                            if deadline.expired():break
                            try:raw=await asyncio.wait_for(ws.recv(),timeout=.2)
                            except asyncio.TimeoutError:raw=None
                            if raw:
                                pong=raw in ('PONG',b'PONG')
                                liveness.received(time.monotonic(),pong=pong)
                                if pong:
                                    emit('feed_liveness',{'venue':venue,'session_id':session,
                                         'trigger':'application_pong',**liveness.evidence(time.monotonic())})
                                    raw=None
                            if raw and raw!='PONG':
                                value=json.loads(raw)
                                for payload in (value if isinstance(value,list) else [value]):
                                    at=time.time();frame_counter+=1
                                    persist_raw=True
                                    if venue=='kalshi':
                                        payload_type=payload.get('type')
                                        if payload_type=='rfq_created':
                                            rfq_legs=payload.get('msg',{}).get('mve_selected_legs') or []
                                            persist_raw=collection_candidate(rfq_legs, config)
                                        else:
                                            persist_raw=payload_type in ('subscribed','error')
                                    reference=emit(venue,payload,at) if persist_raw else f'{venue}:{run}:frame:{frame_counter}'
                                    # The trade channel can produce hundreds of
                                    # thousands of frames per minute. Raw trade
                                    # frames belong in the dedicated RFQ/trade
                                    # sniffer; the bounded runtime retains only
                                    # frames needed to audit RFQs, subscriptions,
                                    # lifecycle changes, and feed errors.
                                    if venue=='kalshi':
                                        if payload.get('type')=='error':raise ValueError('subscription_error')
                                        msg=payload.get('msg',{})
                                        if payload.get('type')=='trade' and (config.get('inventory_fitting') or {}).get('paper_trade_matching') and msg.get('market_ticker') in recent:
                                            emit('paper_trade',dict(msg,source_reference=reference),at)
                                        if payload.get('type')=='subscribed' and msg.get('channel')=='orderbook_delta':book_sid=msg['sid']
                                        if payload.get('type')=='rfq_created':
                                            legs=msg.get('mve_selected_legs') or []
                                            if collection_candidate(legs, config):
                                                recent[msg['market_ticker']]=at
                                                for leg in legs:recent_legs[leg['market_ticker']]=at
                                                if probe_config and probe_config.get('demand_priority'):
                                                    emit('rfq_refresh_demand',{'rfq_id':msg['id'],'market_tickers':sorted({l['market_ticker'] for l in legs}),'source_reference':reference},at)
                                    book_payload=probe.filter_rebuild_frame(payload) if probe else payload
                                    for kind,row in books.consume(book_payload,at,reference):
                                        if probe and kind=='observation':
                                            row.update(probe.observe(market_tokens[row['market_key']],row))
                                        emit(kind,row,at)
                                    if refresh and payload.get('type') in ('orderbook_snapshot','orderbook_delta'):
                                        refresh.observed(payload['msg']['market_ticker'],time.monotonic())
                            now=time.monotonic()
                            if probe:
                                if demand and now-last_demand_poll>=1:
                                    probe.demand=demand.poll(store.db,time.time());last_demand_poll=now
                                try:
                                    probe.tick(books,emit)
                                    rebuild=probe.rebuild_targets(books)
                                    if rebuild:
                                        # Publish inactive observations before changing subscriptions.
                                        flush()
                                        await send({'operation':'unsubscribe','assets_ids':rebuild})
                                        await send({'operation':'subscribe','assets_ids':rebuild,'custom_feature_enabled':True})
                                        emit('book_rebuild',{'tokens':rebuild,'status':'requested','session_id':session})
                                        flush()
                                except (BookResyncRequired,SnapshotRecoveryExhausted):
                                    # Invalidate consumers before waiting for socket closure.
                                    emit('venue_reset',{'venue':venue,'reason':'snapshot_depth_mismatch',
                                        'session_id':session});flush()
                                    raise
                            if refresh and book_sid is not None:
                                demanded={t for t,at in recent_legs.items() if 0<=time.time()-at<60}
                                refresh_targets=refresh.choose(static & requested,now,demanded)
                                if refresh_targets:
                                    emit('kalshi_refresh_selection',{'market_tickers':refresh_targets,
                                        'demanded_tickers':sorted(set(refresh_targets)&demanded),
                                        'demand_priority':refresh.demand_priority})
                                    command+=1
                                    await send({'id':command,'cmd':'update_subscription','params':{
                                        'sids':[book_sid],'market_tickers':refresh_targets,'action':'get_snapshot'}})
                            if venue=='polymarket' and now-last_ping>=10 and liveness.pending_ping is None:
                                await ws.send('PING');last_ping=now;liveness.ping_sent(now)
                            if now-last_heartbeat>=1:
                                emit('heartbeat',{'venue':venue,'session_id':session,'subscribed_books':len(requested),
                                     'eligible_combo_candidates':len(recent),'combo_subscription_cap':config['maximum_combo_subscriptions'],
                                     'connection_evidence':liveness.evidence(now)})
                                last_heartbeat=now
                            if venue=='kalshi' and now-last_subscription>=1:
                                recent={t:at for t,at in recent.items() if time.time()-at<60}
                                recent_legs={t:at for t,at in recent_legs.items() if time.time()-at<60}
                                desired=static|set(sorted(recent,key=recent.get,reverse=True)[:config['maximum_combo_subscriptions']])|set(sorted(recent_legs,key=recent_legs.get,reverse=True)[:config.get('maximum_unmapped_leg_subscriptions',200)])
                                add=desired-requested;remove=requested-desired
                                if not subscription_sent and add:
                                    command+=1;subscription_sent=True;requested=desired
                                    books.set_targets(desired)
                                    await send({'id':command,'cmd':'subscribe','params':{'channels':['orderbook_delta'],'market_tickers':sorted(desired)}})
                                elif book_sid is not None:
                                    for action,markets in (('delete_markets',remove),('add_markets',add)):
                                        if markets:
                                            command+=1
                                            await send({'id':command,'cmd':'update_subscription','params':{'sids':[book_sid],'market_tickers':sorted(markets),'action':action}})
                                    for ticker in remove:
                                        emit('combo_book' if ticker.startswith('KXMVE') else 'unmapped_book',
                                             {'market_ticker':ticker,'valid':False,'observed_at':time.time(),'reason':'subscription_evicted'})
                                    books.set_targets(desired)
                                    requested=desired
                                last_subscription=now
                            if len(pending)>=500 or now-last_flush>=.1:flush()
                except asyncio.CancelledError:raise
                except SnapshotRecoveryExhausted:
                    emit('venue_reset',{'venue':venue,'reason':'snapshot_recovery_budget_exhausted','session_id':session});flush()
                    raise
                except Exception as exc:
                    emit('venue_reset',{'venue':venue,'reason':'disconnected','error_type':type(exc).__name__,
                        'diagnostic':str(exc) if isinstance(exc,(KeyError,ValueError)) else None,'session_id':session});flush()
                    await asyncio.sleep(retry);retry=min(30,retry*2)
    except TimeoutError:pass
    finally:
        if probe:await probe.close()
        emit('capture_timing',{'venue':venue,'requested_seconds':seconds,**deadline.elapsed()})
        emit('venue_reset',{'venue':venue,'reason':'collector_stopped'});flush();store.close()
