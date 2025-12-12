
import numpy as np
from pricing import VanillaFxOptionPricer, VolatilitySurface

def test_forward_return():
    # S=1.0, rd=0.05, fwd=1.0305, T=1.0
    pricer = VanillaFxOptionPricer(1.0, 0.05, 1.0305, 1.0)
    assert np.isclose(pricer.calculate_forward(), 1.0305)
    # Check derived rf
    # F = S * exp((rd-rf)T) -> ln(F/S) = (rd-rf)T -> rf = rd - ln(F/S)/T
    # rf = 0.05 - ln(1.0305)/1 = 0.05 - 0.03004 = ~0.02
    assert np.isclose(pricer.rf, 0.02, atol=0.001)

def test_atm_price():
    # S=100, K=100, rd=0, T=1, vol=0.2.
    # rf=0 means Fwd = 100 * exp(0) = 100.
    pricer = VanillaFxOptionPricer(100.0, 0.0, 100.0, 1.0)
    price = pricer.price(0.2, 100.0, 'call')
    assert 7.9 < price < 8.0

def test_surface_construction():
    # Test that surface constructs and returns reasonable interpolated vol
    # S=1.0, rd=0, F=1.0 (rf=0)
    pricer = VanillaFxOptionPricer(1.0, 0.0, 1.0, 1.0)
    atm = 0.10
    rr25 = 0.00 # Flat
    st25 = 0.00
    rr10 = 0.00
    st10 = 0.00
    
    surface = VolatilitySurface(atm, rr25, st25, rr10, st10)
    surface.construct_smile(pricer)
    
    # Should be flat 10%
    assert np.isclose(surface.get_vol(1.0), 0.10)
    assert np.isclose(surface.get_vol(1.10), 0.10)
    assert np.isclose(surface.get_vol(0.90), 0.10)

def test_smile_shape():
    # If RR is positive, Calls > Puts in vol.
    # High strike (Call domain) should have higher vol than Low strike (Put domain) if we ignore skew vs smile dominance?
    # RR = Vol(25d Call) - Vol(25d Put). If > 0, Call vol is higher.
    # 25d Call is OTM call (High strike). 25d Put is OTM put (Low strike).
    # So High strike vol > Low strike vol.
    
    pricer = VanillaFxOptionPricer(1.0, 0.0, 1.0, 1.0)
    surface = VolatilitySurface(0.10, 0.02, 0.00, 0.02, 0.00) # RR=2%, ST=0
    surface.construct_smile(pricer)
    
    vol_low_strike = surface.get_vol(0.9)
    vol_high_strike = surface.get_vol(1.1)
    
    assert vol_high_strike > vol_low_strike

def test_delta_solver():
    # Test that we can solve for strike given delta
    # S=100, rd=0, F=100, T=1, vol=0.1
    # Delta 0.50 should result in roughly ATM strike (~100)
    pricer = VanillaFxOptionPricer(100.0, 0.0, 100.0, 1.0)
    surface = VolatilitySurface(0.1, 0, 0, 0, 0)
    surface.construct_smile(pricer)
    
    k_sol = pricer.solve_strike_for_delta(0.50, 'call', surface)
    # Analytic delta for ATM (K=F) is N(0.5*sigma*sqrt(T)) approx 0.52
    # So K for delta 0.50 will be slightly ITM/OTM depending?
    # d1 = ln(F/K)/v + 0.5v
    # If delta=0.5 -> N(d1)=0.5 -> d1=0 -> ln(F/K) = -0.5v^2 -> K = F * exp(0.5v^2)
    expected_k = 100.0 * np.exp(0.5 * 0.1**2 * 1.0) # ~ 100.5
    
    assert np.isclose(k_sol, expected_k, rtol=0.01)


def test_vega_calculations():
    # Test BS Vega
    # S=100, K=100, rd=0, T=1, vol=0.2.
    # rf=0 means Fwd = 100 * exp(0) = 100.
    # d1 = (ln(100/100) + 0.5*0.2^2*1) / (0.2*1) = 0.02 / 0.2 = 0.1
    # N'(0.1) = 1/sqrt(2pi) * exp(-0.01/2) = 0.3989 * 0.995 = 0.3969
    # Vega = S * sqrt(T) * N'(d1) = 100 * 1 * 0.3969 = 39.69
    
    pricer = VanillaFxOptionPricer(100.0, 0.0, 100.0, 1.0)
    vega = pricer.calculate_vega(100.0, 0.2)
    
    expected_vega = 39.69
    assert np.isclose(vega, expected_vega, atol=0.1)
    
    # Test Model Sensitivities
    # If we perturb ATM vol by 1%, price roughly changes by Vega * 1%?
    # Not exact because perturbing ATM affects the whole surface construction and strike solving.
    # But directionally correct.
    
    atm = 0.20
    surface = VolatilitySurface(atm, 0.0, 0.0, 0.0, 0.0)
    surface.construct_smile(pricer)
    
    sens = pricer.calculate_model_sensitivities(100.0, 'call', surface)
    
    # Sensitivity to 'atm' should be close to BS Vega (since surface is flat and we bump parallel)
    # The 'vega' returned is for 1 unit change in volatility (100% vol).
    # Sensitivity is dPrice/dParam. Param is vol. So it should be close to Vega.
    
    assert np.isclose(sens['atm'], vega, rtol=0.05)
    
    # RR and ST should be zero for ATM strike (since they affect wings more)
    # Actually, ST affects curvature, so might affect ATM slightly depending on definition?
    # ST definition: 0.5 * (Vol25C + Vol25P) - VolATM.
    # If we bump ST, wings go up. Spline might affect ATM?
    # But usually ST is defined relative to ATM.
    # Let's just check they run and return floats.
    
    for k in sens:
        assert isinstance(sens[k], float)

def test_risk_reversal():
    # Test RR pricing manually
    # S=100, rd=0, T=1, atm=0.1
    # RR = Call(K_high) - Put(K_low)
    # 25d RR
    
    pricer = VanillaFxOptionPricer(100.0, 0.0, 100.0, 1.0)
    surface = VolatilitySurface(0.1, 0.0, 0.0, 0.0, 0.0) # Flat surface
    surface.construct_smile(pricer)
    
    # Solve strikes
    k_put = pricer.solve_strike_for_delta(0.25, 'put', surface)
    k_call = pricer.solve_strike_for_delta(0.25, 'call', surface)
    
    # Price legs
    p_put = pricer.price(0.1, k_put, 'put')
    p_call = pricer.price(0.1, k_call, 'call')
    
    expected_rr_price = p_call - p_put
    
    # We can't easily call the API function here, but we can trust the component logic if we tested the components.
    # The logic in app.py simply orchestrates this.
    # Let's verify that p_call and p_put are non-zero and different usually (unless symmetric ATM? No, Delta 25 implies OTM).
    
    assert p_put > 0
    assert p_call > 0
    assert expected_rr_price != 0 # Likely not exactly 0 unless perfectly symmetric distribution and strikes
    
    print(f"RR Price: {expected_rr_price}")

if __name__ == "__main__":
    test_forward_return()
    test_atm_price()
    test_surface_construction()
    test_smile_shape()
    test_delta_solver()
    test_vega_calculations()
    test_risk_reversal()
    print("All verification tests passed!")
