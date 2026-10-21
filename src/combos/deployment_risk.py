"""Optional fixed deployment ceiling, separate from settled account equity.

This candidate ledger is not yet wired into historical runners or live runtime.
It uses the existing transaction and reservation lifecycle without schema changes.
"""
from decimal import Decimal, ROUND_FLOOR

from .risk import RiskLedger, units


class DeploymentCappedRiskLedger(RiskLedger):
    def __init__(self, store, policy):
        ceiling = Decimal(str(policy['maximum_committed_dollars']))
        if not ceiling.is_finite() or ceiling <= 0:
            raise ValueError('deployment ceiling must be finite and positive')
        self.ceiling_units = int((ceiling * 10000).to_integral_value(rounding=ROUND_FLOOR))
        if self.ceiling_units <= 0:
            raise ValueError('deployment ceiling below ledger precision')
        super().__init__(store, policy)

    def deployment_headroom(self):
        committed = self.db.execute(
            "SELECT COALESCE(SUM(cost),0) FROM reservations "
            "WHERE status IN ('reserved','simulated_filled')"
        ).fetchone()[0]
        return self.ceiling_units - committed

    def available(self):
        """Spendable reservation allowance: cash and deployment must both fit."""
        return min(super().available(), self.deployment_headroom())

    def reserve(self, identifier, creator, cost_dollars, buckets, expires_at,
                context, limit_multiplier=1., signed_buckets=None):
        result = super().reserve(identifier, creator, cost_dollars, buckets,
                                 expires_at, context, limit_multiplier, signed_buckets)
        if result.get('reason') == 'capital_exhausted':
            cost = units(cost_dollars)
            result['binding_funding_limits'] = []
            if cost > super().available():
                result['binding_funding_limits'].append('settled_cash')
            if cost > self.deployment_headroom():
                result['binding_funding_limits'].append('deployment_ceiling')
                result['reason'] = 'deployment_cash_limit'
        result['deployment_headroom_dollars'] = self.deployment_headroom() / 10000
        result['settled_cash_available_dollars'] = super().available() / 10000
        return result
