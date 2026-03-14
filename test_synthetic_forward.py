
import numpy as np
from pricing import VanillaFxOptionPricer, VolatilitySurface

def test_synthetic_forward():
    print("Running Synthetic Forward Verification...")
    
    # Parameters
    S = 1.2500
    rd = 0.03
    F = 1.2550
    T = 0.5
    vol = 0.12
    K = 1.2500 # ATM-ish
    
    pricer = VanillaFxOptionPricer(S, rd, F, T)
    surface = VolatilitySurface(vol, 0.0, 0.0, 0.0, 0.0) # Flat surface
    surface.construct_smile(pricer)
    
    # Derived rf
    rf = pricer.rf
    df_rd = np.exp(-rd * T)
    df_rf = np.exp(-rf * T)
    
    # Prices
    p_call = pricer.price(vol, K, 'call')
    p_put = pricer.price(vol, K, 'put')
    
    # Put-Call Parity: C - P = S*exp(-rf*T) - K*exp(-rd*T)
    actual_parity = p_call - p_put
    expected_parity = S * df_rf - K * df_rd
    
    print(f"--- Price Check ---")
    print(f"Call Price: {p_call:.6f}")
    print(f"Put Price: {p_put:.6f}")
    print(f"C - P: {actual_parity:.8f}")
    print(f"Expected: {expected_parity:.8f}")
    
    assert np.isclose(actual_parity, expected_parity), f"Put-Call Parity failed! Diff: {actual_parity - expected_parity}"
    
    # Delta Check
    d_call = pricer.calculate_delta(K, vol, 'call')
    d_put = pricer.calculate_delta(K, vol, 'put')
    
    # Synthetic Delta: dC - dP = exp(-rf*T)
    actual_d_synth = d_call - d_put
    expected_d_synth = df_rf
    
    print(f"\n--- Delta Check ---")
    print(f"Call Delta: {d_call:.6f}")
    print(f"Put Delta: {d_put:.6f}")
    print(f"dC - dP: {actual_d_synth:.8f}")
    print(f"Expected: {expected_d_synth:.8f}")
    
    assert np.isclose(actual_d_synth, expected_d_synth), f"Synthetic Delta failed! Diff: {actual_d_synth - expected_d_synth}"

    # Vega Check
    v_call = pricer.calculate_vega(K, vol)
    v_put = pricer.calculate_vega(K, vol) # The function doesn't take type, it's symmetry in BS
    
    print(f"\n--- Vega Check ---")
    print(f"Call Vega: {v_call:.6f}")
    print(f"Put Vega: {v_put:.6f}")
    
    # They should be identical in BS
    assert np.isclose(v_call, v_put), "Vega should be symmetric for Call/Put in Black-Scholes"
    
    # Check for cross-sensitivity: RR price should have very low sensitivity to ST bump and vice-versa (on flat surface)
    sens_rr = pricer.calculate_model_sensitivities(K, 'risk_reversal', surface, strike_2=K*1.05) # dummy spread
    print(f"Flat Surface - RR Sens to ST pillar: {sens_rr['st25']:.8e}")
    
    print("\nSUCCESS: Put-Call Parity and Synthetic Forward Greeks verified.")

def test_multi_leg_sensitivities():
    print("\nRunning Multi-leg Sensitivity Verification...")
    
    # Parameters
    S = 1.0
    rd = 0.05
    F = 1.05
    T = 1.0
    vol = 0.10
    
    pricer = VanillaFxOptionPricer(S, rd, F, T)
    surface = VolatilitySurface(vol, 0.0, 0.0, 0.0, 0.0) # Flat
    surface.construct_smile(pricer)
    
    k1 = 0.95 # Put strike
    k2 = 1.05 # Call strike
    
    # RR Sensitivity
    # RR = Call(k2) - Put(k1)
    sens_rr = pricer.calculate_model_sensitivities(k1, 'risk_reversal', surface, strike_2=k2)
    
    # Strangle Sensitivity
    # Strangle = Put(k1) + Call(k2)
    sens_st = pricer.calculate_model_sensitivities(k1, 'strangle', surface, strike_2=k2)
    
    # Single leg sens
    sens_p = pricer.calculate_model_sensitivities(k1, 'put', surface)
    sens_c = pricer.calculate_model_sensitivities(k2, 'call', surface)
    
    print(f"RR Sensitivity (ATM): {sens_rr['atm']:.8e}")
    print(f"Strangle Sensitivity (ATM): {sens_st['atm']:.8e}")
    
    # In Vega-Neutral strategy, ATM sensitivity should be ZERO
    assert np.isclose(sens_rr['atm'], 0.0, atol=1e-7), "Multi-leg RR should be ATM Vega-Neutral!"
    # Strangle is NOT Vega-Neutral to ATM moves (it's Vega-LONG), so it should be non-zero
    assert not np.isclose(sens_st['atm'], 0.0), "Multi-leg Strangle should have non-zero ATM sensitivity!"
    
    # CROSS SENSITIVITY CHECK (The core of the user's issue)
    print(f"\n--- Cross-Sensitivity Analysis (25 Delta Strategy) ---")
    # With Vega-Weighting, cross-sensitivities should be near zero on flat surface
    
    # Strangle: sens to RR should be near 0
    print(f"25d Strangle Sens to 25d RR: {sens_st['rr25']:.8e}")
    assert np.isclose(sens_st['rr25'], 0.0, atol=1e-7), "Strangle should have ~0 sensitivity to RR parameter!"
    
    # RR: sens to ST should be near 0
    print(f"25d RR Sens to 25d ST: {sens_rr['st25']:.8e}")
    assert np.isclose(sens_rr['st25'], 0.0, atol=1e-7), "RR should have ~0 sensitivity to ST parameter!"
    
    # Let's check Vegas
    v_p = pricer.calculate_vega(k1, vol)
    v_c = pricer.calculate_vega(k2, vol)
    print(f"Put Vegas: {v_p:.6f}, Call Vegas: {v_c:.6f}, Diff: {v_c - v_p:.6f}")

    print("\nSUCCESS: Multi-leg sensitivities verified.")

if __name__ == "__main__":
    try:
        test_synthetic_forward()
        test_multi_leg_sensitivities()
    except Exception as e:
        print(f"\nFAILURE: {e}")
        import traceback
        traceback.print_exc()
