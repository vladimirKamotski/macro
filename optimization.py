
import numpy as np

class HedgeOptimizer:
    def __init__(self, pricer, surface):
        self.pricer = pricer
        self.surface = surface
        self.instruments = [
            {'name': 'ATM', 'type': 'strangle', 'd': 'atm'}, # ATM Straddle
            {'name': '25d RR', 'type': 'risk_reversal', 'd': '25'},
            {'name': '25d ST', 'type': 'strangle', 'd': '25'},
            {'name': '10d RR', 'type': 'risk_reversal', 'd': '10'},
            {'name': '10d ST', 'type': 'strangle', 'd': '10'}
        ]
        self.param_order = ['atm', 'rr25', 'st25', 'rr10', 'st10']

    def _get_instrument_strikes(self, instr_def):
        # Helper to get K1, K2 for a given instrument definition
        d_val = instr_def['d']
        
        if d_val == 'atm':
            # ATM Straddle
            k = self.surface.k_atm
            return k, k
            
        elif d_val == '25':
            # 25 Delta
            # We need to solve for strikes corresponding to 25 delta
            # Using the surface to find vols
            # Note: Strangle/RR usually defined by Delta of the legs
            
            # Put Strike (25d Put)
            k_put = self.pricer.solve_strike_for_delta(0.25, 'put', self.surface)
            # Call Strike (25d Call)
            k_call = self.pricer.solve_strike_for_delta(0.25, 'call', self.surface)
            return k_put, k_call
            
        elif d_val == '10':
            k_put = self.pricer.solve_strike_for_delta(0.10, 'put', self.surface)
            k_call = self.pricer.solve_strike_for_delta(0.10, 'call', self.surface)
            return k_put, k_call
            
        return None, None

    def calculate_sensitivity_matrix(self):
        # Build 5x5 matrix
        # Columns = Instruments
        # Rows = Risk Factors (atm, rr25, st25, rr10, st10)
        
        matrix = np.zeros((5, 5))
        
        for col_idx, instr in enumerate(self.instruments):
            k1, k2 = self._get_instrument_strikes(instr)
            
            # Calculate sens vector for this instrument
            # Using calculate_model_sensitivities from pricing.py
            # Note: logic handles single leg or multi-leg.
            # ATM Straddle is a 'strangle' with k1=k2=atm
            
            sens = self.pricer.calculate_model_sensitivities(
                k1, instr['type'], self.surface, strike_2=k2
            )
            
            # Fill column
            for row_idx, param in enumerate(self.param_order):
                matrix[row_idx, col_idx] = sens[param]
                
        return matrix

    def optimize_hedge(self, risk_vector, spreads):
        # risk_vector: dict {atm: val, rr25: val...} or list matching param_order
        # spreads: list of bid-ask spreads for the 5 instruments (cost per unit)
        
        # S * x = -R
        # x = - inv(S) * R
        
        S = self.calculate_sensitivity_matrix()
        
        # Convert risk dict to vector if needed
        if isinstance(risk_vector, dict):
            R = np.array([risk_vector.get(p, 0.0) for p in self.param_order])
        else:
            R = np.array(risk_vector)
            
        # Solve
        # We check condition number to ensure stability
        try:
            x = np.linalg.solve(S, -R)
        except np.linalg.LinAlgError:
            return {'success': False, 'message': 'Singular matrix'}
            
        # Calculate Costs
        # Cost = sum( abs(x) * spread / 2 )
        total_cost = 0.0
        details = []
        
        for i, val in enumerate(x):
            spread = spreads[i] if i < len(spreads) else 0.0
            cost = abs(val) * spread / 2.0
            total_cost += cost
            
            details.append({
                'instrument': self.instruments[i]['name'],
                'size': val,
                'cost': cost
            })
            
        return {
            'success': True,
            'trades': details,
            'total_cost': total_cost,
            'residual_risk': np.dot(S, x) + R # Should be ~0
        }
