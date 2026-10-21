import pytest
from combos.rfq_scenario_consumer import RFQScenarioConsumer
from combos.weighted_fair import WeightPolicy


def test_requires_shadow_and_owns_configuration():
    with pytest.raises(ValueError):RFQScenarioConsumer({'mode':'live'},[],WeightPolicy())
    config={'mode':'shadow','mappings':[]};c=RFQScenarioConsumer(config,[],WeightPolicy())
    config['mappings'].append({'malformed':True})
    assert c.runtime['mappings']==[]


def test_state_cannot_consume_events_out_of_order():
    c=RFQScenarioConsumer({'mode':'shadow','mappings':[]},[],WeightPolicy())
    event={'seq':1,'received_at':1,'kind':'heartbeat','source':'test','payload':{}}
    assert c.consume(event) is None
    with pytest.raises(ValueError):c.consume(event)


def test_logging_flag_requires_boolean():
    with pytest.raises(ValueError,match='logging flag'):
        RFQScenarioConsumer({'mode':'shadow','mappings':[],'record_venue_components':'false'},[],WeightPolicy())
