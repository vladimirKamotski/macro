
from flask import Flask, render_template, request, jsonify
import numpy as np
from pricing import VanillaFxOptionPricer, VolatilitySurface

app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/calculate', methods=['POST'])
def calculate():
    try:
        data = request.json
        
        # Parse inputs
        spot_ref = float(data.get('spot_ref', 1.0))
        rd = float(data.get('rd', 0.0))
        # rf -> replaced by forward
        forward = float(data.get('forward', 1.0)) # Default to spot if not provided?
        T = float(data.get('T', 1.0))
        
        # Vol constants
        atm = float(data.get('atm', 0.1))
        rr25 = float(data.get('rr25', 0.0))
        st25 = float(data.get('st25', 0.0))
        rr10 = float(data.get('rr10', 0.0))
        st10 = float(data.get('st10', 0.0))
        
        # Contract
        strike_input = float(data.get('strike', 1.0))
        strike_type = data.get('strike_type', 'price') # 'price' or 'delta'
        option_type = data.get('type', 'call')
        
        # Init pricer with forward
        pricer = VanillaFxOptionPricer(spot_ref, rd, forward, T)
        
        # Construct surface
        surface = VolatilitySurface(atm, rr25, st25, rr10, st10)
        surface.construct_smile(pricer)
        
        # Determine actual strike
        # Determine actual strike(s)
        strike_2 = None # For Strangle by Price
        
        if option_type == 'strangle':
            if strike_type == 'delta':
                # Symmetric Delta Strangle (e.g. 25 Delta -> 25d Put + 25d Call)
                # Solve for Put Strike (Delta = -strike_input, or abs=strike_input)
                k_put = pricer.solve_strike_for_delta(strike_input, 'put', surface)
                k_call = pricer.solve_strike_for_delta(strike_input, 'call', surface)
                
                if k_put is None or k_call is None:
                    return jsonify({'success': False, 'message': 'Could not solve strikes for strangle delta'}), 400
                
                strike = k_put # We'll report both or just the first? Let's treat 'strike' as K_put and 'strike_2' as K_call for reporting
                strike_2 = k_call
                
            else:
                # Strangle by Price
                # strike_input is Put Strike (K_low)
                # Data should have strike_2 for Call Strike (K_high)
                strike_2_input = float(data.get('strike_2', strike_input)) # Fallback to same if missing
                strike = strike_input
                strike_2 = strike_2_input
                
            # Price Strangle = Price(Put, K_put) + Price(Call, K_call)
            vol_put = surface.get_vol(strike)
            vol_call = surface.get_vol(strike_2)
            
            p_put = pricer.price(vol_put, strike, 'put')
            p_call = pricer.price(vol_call, strike_2, 'call')
            
            price = p_put + p_call
            
            # Weighted vol? Or average? 
            # Usually return separate vols or just one representative. Let's return avg or list?
            # Existing specific 'vol' field expects float. Let's return average for now or just vol_put.
            interp_vol = (vol_put + vol_call) / 2.0 
            
        elif option_type == 'risk_reversal':
            # Risk Reversal = Long Call (High K) - Short Put (Low K)
            # Usually defined by Delta (e.g. 25 Delta RR = 25d Call - 25d Put)
            
            if strike_type == 'delta':
                # Symmetric Delta (e.g. 25 Delta -> 25d Put + 25d Call)
                # Solve for Put Strike (Delta = -strike_input)
                # Solve for Call Strike (Delta = strike_input)
                k_put = pricer.solve_strike_for_delta(strike_input, 'put', surface)
                k_call = pricer.solve_strike_for_delta(strike_input, 'call', surface)
                
                if k_put is None or k_call is None:
                    return jsonify({'success': False, 'message': 'Could not solve strikes for RR delta'}), 400
                
                strike = k_put # Low Strike (Short Put)
                strike_2 = k_call # High Strike (Long Call)
                
            else:
                # RR by Price
                # strike_input = Put Strike (K_low)
                # strike_2_input = Call Strike (K_high)
                strike_2_input = float(data.get('strike_2', strike_input)) 
                strike = strike_input
                strike_2 = strike_2_input
            
            # Price RR = Price(Call, K_call) - Price(Put, K_put)
            vol_put = surface.get_vol(strike)
            vol_call = surface.get_vol(strike_2)
            
            p_put = pricer.price(vol_put, strike, 'put')
            p_call = pricer.price(vol_call, strike_2, 'call')
            
            price = p_call - p_put
            
            interp_vol = (vol_put + vol_call) / 2.0
            
        elif strike_type == 'delta':
            # ... existing single leg delta logic ...
            # strike_input is treated as delta (e.g. 0.25)
            # Cap at reasonable values 0 < delta < 1
            if strike_input <= 0 or strike_input >= 1:
                 return jsonify({'success': False, 'message': 'Delta must be between 0 and 1'}), 400
                 
            solved_k = pricer.solve_strike_for_delta(strike_input, option_type, surface)
            if solved_k is None:
                return jsonify({'success': False, 'message': 'Could not solve strike for given delta'}), 400
            strike = solved_k
            interp_vol = surface.get_vol(strike)
            price = pricer.price(interp_vol, strike, option_type)
            
        else:
            # Single leg by Price
            strike = strike_input
            interp_vol = surface.get_vol(strike)
            price = pricer.price(interp_vol, strike, option_type)
        
        
        # Prepare Plot Data
        # Prepare Plot Data
        # Knots: [10d Put, 25d Put, ATM, 25d Call, 10d Call]
        # User requested: 10d, 25d, ATM, 75d, 90d (implying Call Deltas)
        # 10d Put ~ 90d Call
        # 25d Put ~ 75d Call
        knots_x = surface.strikes
        knots_y = surface.vols
        # Assuming sorted: [0]=10dPut (Low K), [1]=25dPut, [2]=ATM, [3]=25dCall, [4]=10dCall (High K)
        # User requested sequence: 10, 25, ATM, 75, 90 (Likely mapping Low K to 10d and High K to 90d?)
        # Or simply preferring ascending delta labels (Put Delta -> Call Delta convention mix?)
        labels = ["10 Delta", "25 Delta", "ATM", "75 Delta", "90 Delta"]
        
        # Curve generation
        min_k = knots_x[0] * 0.8
        max_k = knots_x[-1] * 1.2
        curve_x = np.linspace(min_k, max_k, 50).tolist()
        curve_y = [surface.get_vol(k) for k in curve_x]
        
        # Calculate Sensitivities
        bs_vega = pricer.calculate_vega(strike, interp_vol)
        model_sens = pricer.calculate_model_sensitivities(strike, option_type, surface)
        
        # Calculate Payoff Curve (at Maturity) vs Spot
        # Use same range as curve_x (strikes) but treated as Spot prices
        spot_range = curve_x 
        payoff_y = []
        
        for s_val in spot_range:
            val = 0.0
            if option_type == 'strangle':
                # Put (K_low) + Call (K_high)
                # K_low = strike, K_high = strike_2
                # Payoff = max(K_low - S, 0) + max(S - K_high, 0)
                val = max(strike - s_val, 0) + max(s_val - strike_2, 0)
                
            elif option_type == 'risk_reversal':
                # Long Call (K_high) - Short Put (K_low)
                # K_low = strike, K_high = strike_2
                val = max(s_val - strike_2, 0) - max(strike - s_val, 0)

            elif option_type == 'call':
                val = max(s_val - strike, 0)
            elif option_type == 'put':
                val = max(strike - s_val, 0)
            
            payoff_y.append(val)

        return jsonify({
            'success': True,
            'price': price,
            'vol': interp_vol,
            'forward': pricer.calculate_forward(),
            'strike_used': strike,
            'strike_2_used': strike_2 if strike_2 else None,
            'atm_strike': getattr(surface, 'k_atm', None),
            'vega': bs_vega,
            'model_vega': model_sens,
            'message': 'Priced successfully',
            'plot_data': {
                'curve_x': curve_x,
                'curve_y': curve_y,
                'payoff_x': spot_range,
                'payoff_y': payoff_y,
                'points_x': knots_x,
                'points_y': knots_y,
                'point_labels': labels
            }
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True, port=5001)
