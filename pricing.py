
import numpy as np
from scipy.stats import norm
from scipy.optimize import brentq
from scipy.interpolate import CubicSpline

class VanillaFxOptionPricer:
    def __init__(self, spot, domestic_rate, forward_rate, time_to_maturity):
        self.S = float(spot)
        self.rd = float(domestic_rate)
        self.F = float(forward_rate)
        self.T = float(time_to_maturity)
        self.year_fraction = 365.0
        
        # Derive rf for delta calculations
        # F = S * exp((rd - rf) * T) -> rf = rd - ln(F/S)/T
        if self.T > 0 and self.S > 0 and self.F > 0:
            self.rf = self.rd - np.log(self.F / self.S) / self.T
        else:
            self.rf = 0.0 # Fallback or handle standard expiration
            
    def copy(self):
        # Helper to clone pricer
        return VanillaFxOptionPricer(self.S, self.rd, self.F, self.T)

    def calculate_forward(self):
        return self.F

    def d1(self, K, sigma):
        if self.T <= 0 or sigma <= 0:
            return 0
        F = self.calculate_forward()
        return (np.log(F / K) + 0.5 * sigma**2 * self.T) / (sigma * np.sqrt(self.T))

    def d2(self, K, sigma):
        return self.d1(K, sigma) - sigma * np.sqrt(self.T)

    def calculate_vega(self, K, sigma):
        # BS Vega = S * exp(-rf*T) * sqrt(T) * N'(d1)
        # N'(d1) = (1/sqrt(2pi)) * exp(-d1^2 / 2)
        if self.T <= 0:
            return 0.0
        d_1 = self.d1(K, sigma)
        # Using Spot Vega (sensitivity to change in vol, usually for spot price but here it's simple BS Vega)
        # Vega = dV / dSigma
        # Standard formulas often use df_rd for equity, but for FX it's df_rf * S ... check math
        # FX Option Price V = S * exp(-rf*T) * N(d1) - K * exp(-rd*T) * N(d2)
        # dV/dSigma = S * exp(-rf*T) * N'(d1) * sqrt(T)
        
        df_rf = np.exp(-self.rf * self.T)
        # norm.pdf is N'
        vega = self.S * df_rf * np.sqrt(self.T) * norm.pdf(d_1)
        return vega

    def price(self, sigma, K, option_type='call'):
        F = self.calculate_forward()
        d_1 = self.d1(K, sigma)
        d_2 = self.d2(K, sigma)
        
        df = np.exp(-self.rd * self.T)
        
        if option_type.lower() == 'call':
            return df * (F * norm.cdf(d_1) - K * norm.cdf(d_2))
        else:
            return df * (K * norm.cdf(-d_2) - F * norm.cdf(-d_1))

    def calculate_delta(self, K, sigma, option_type='call'):
        # Delta = dV/dS
        # Call Delta = exp(-rf*T) * N(d1)
        # Put Delta = exp(-rf*T) * (N(d1) - 1)
        # Note: This is "Spot Delta".
        d_1 = self.d1(K, sigma)
        df_rf = np.exp(-self.rf * self.T)
        
        if option_type.lower() == 'call':
            return df_rf * norm.cdf(d_1)
        else:
            return df_rf * (norm.cdf(d_1) - 1.0)

    def solve_strike_for_delta(self, target_delta, option_type, surface):
        # target_delta: e.g. 0.25
        # option_type: 'call' or 'put'
        # surface: VolatilitySurface object
        
        # We want to find K such that abs(calculate_delta(K, surface.get_vol(K))) == target_delta
        # Note: Put delta is negative usually.
        # If user passes positive delta for put (e.g. 25 Delta Put), we target -0.25 (or just match abs).
        # Let's assume input target_delta is positive (e.g. 0.25).
        
        target = target_delta
        if option_type.lower() == 'put':
            target = -target_delta # Standard definition: Put delta is negative
            
        def objective(K):
            if K <= 1e-6: return 999
            vol = surface.get_vol(K)
            d = self.calculate_delta(K, vol, option_type)
            return d - target
            
        # Range scan or broad bounds
        # K usually around Forward.
        F = self.calculate_forward()
        try:
            # Search from very low to very high strike
            # If target delta is very high (ITM), strike is low (Call) or high (Put)
            k_sol = brentq(objective, F * 0.1, F * 5.0)
            return k_sol
        except Exception as e:
            print(f"Solver failed: {e}")
            return None

    def get_delta_strike(self, delta, sigma, option_type='call'):
        # Inverse delta to find strike
        # Delta_call = exp(-rf*T) * N(d1)
        # Delta_put = exp(-rf*T) * (N(d1) - 1)
        # We need to solve for K.
        # This is a bit circular because d1 depends on K, which we want, but also sigma, which technically depends on K (smile).
        # For the purpose of "standard market convention", usually one solves for K assuming a fixed sigma for that delta quote.
        
        chk = np.exp(-self.rf * self.T)
        
        # d1_target
        if option_type == 'call':
             # delta = chk * N(d1) -> N(d1) = delta / chk
             target = delta / chk
             if target <= 0 or target >= 1: return None # Impossible
             d1_val = norm.ppf(target)
        else:
             # delta = chk * (N(d1) - 1) -> N(d1) = delta/chk + 1
             # NOTE: Put delta is usually quoted as negative, but input delta might be positive convention (e.g. 25 Delta Put = -0.25 actual delta).
             # Let's assume input delta is absolute value (e.g. 0.25).
             target = ( -delta ) / chk + 1
             if target <= 0 or target >= 1: return None
             d1_val = norm.ppf(target)
             
        # d1 = (ln(F/K) + 0.5*v^2*T) / (v*sqrt(T))
        # v*sqrt(T)*d1 = ln(F/K) + 0.5*v^2*T
        # ln(F/K) = v*sqrt(T)*d1 - 0.5*v^2*T
        # K = F / exp( ... )
        
        vol_term = sigma * np.sqrt(self.T)
        log_fk = vol_term * d1_val - 0.5 * sigma**2 * self.T
        K = self.calculate_forward() / np.exp(log_fk)
        return K

    def calculate_model_sensitivities(self, target_strike, option_type, base_surface):
        # Calculate sensitivity of Price to each of the 5 surface parameters
        # atm, rr25, st25, rr10, st10
        
        params = [
            ('atm', base_surface.sigma_atm),
            ('rr25', base_surface.rr_25),
            ('st25', base_surface.st_25),
            ('rr10', base_surface.rr_10),
            ('st10', base_surface.st_10)
        ]
        
        results = {}
        epsilon = 0.0001 # 1 basis point
        
        # Base Price
        # We need to get the vol for the target strike using the base surface
        base_vol = base_surface.get_vol(target_strike)
        base_price = self.price(base_vol, target_strike, option_type)
        
        for name, value in params:
            # Construct perturbed surface
            p_args = {
                'atm_vol': base_surface.sigma_atm,
                'rr_25': base_surface.rr_25,
                'st_25': base_surface.st_25,
                'rr_10': base_surface.rr_10,
                'st_10': base_surface.st_10
            }
            
            # Bump parameter
            if name == 'atm': p_args['atm_vol'] += epsilon
            elif name == 'rr25': p_args['rr_25'] += epsilon
            elif name == 'st25': p_args['st_25'] += epsilon
            elif name == 'rr10': p_args['rr_10'] += epsilon
            elif name == 'st10': p_args['st_10'] += epsilon
            
            # New Surface
            new_surface = VolatilitySurface(
                p_args['atm_vol'], p_args['rr_25'], p_args['st_25'], 
                p_args['rr_10'], p_args['st_10']
            )
            new_surface.construct_smile(self) # Need pricer to solve strikes
            
            # New Price
            new_vol = new_surface.get_vol(target_strike)
            new_price = self.price(new_vol, target_strike, option_type)
            
            # Sensitivity = dPrice / dParam
            # Finite difference
            sens = (new_price - base_price) / epsilon
            results[name] = sens
            
        return results

class VolatilitySurface:
    def __init__(self, atm_vol, rr_25, st_25, rr_10, st_10):
        # Market quotes
        self.sigma_atm = atm_vol
        self.rr_25 = rr_25
        self.st_25 = st_25
        self.rr_10 = rr_10
        self.st_10 = st_10
        
    def construct_smile(self, pricer: VanillaFxOptionPricer):
        # Derived vols
        # RR = Vol(25d Call) - Vol(25d Put)
        # ST = 0.5 * (Vol(25d Call) + Vol(25d Put)) - Vol(ATM)
        # -> Vol(25d Call) = ATM + ST + 0.5*RR
        # -> Vol(25d Put) = ATM + ST - 0.5*RR
        
        vol_25_call = self.sigma_atm + self.st_25 + 0.5 * self.rr_25
        vol_25_put = self.sigma_atm + self.st_25 - 0.5 * self.rr_25
        
        vol_10_call = self.sigma_atm + self.st_10 + 0.5 * self.rr_10
        vol_10_put = self.sigma_atm + self.st_10 - 0.5 * self.rr_10
        
        # Determine strikes for these points
        # Use initial guess of sigma_atm for strike determination? Or use the specific vol?
        # Convention: Use the vol OF that point to determine the strike.
        
        k_atm = pricer.get_delta_strike(0.50, self.sigma_atm, 'call') # Approximate ATM Delta Neutral
        # Technically ATM definition varies (ATMF, ATMS, Delta Neutral). Let's stick to Delta Neutral approx.
        
        k_25_c = pricer.get_delta_strike(0.25, vol_25_call, 'call')
        k_25_p = pricer.get_delta_strike(0.25, vol_25_put, 'put')
        
        k_10_c = pricer.get_delta_strike(0.10, vol_10_call, 'call')
        k_10_p = pricer.get_delta_strike(0.10, vol_10_put, 'put')
        
        self.k_atm = k_atm  # Store for reporting
        
        strikes = [k_10_p, k_25_p, k_atm, k_25_c, k_10_c]
        vols = [vol_10_put, vol_25_put, self.sigma_atm, vol_25_call, vol_10_call]
        
        # Sort just in case (Put strikes < Call strikes usually)
        points = sorted(zip(strikes, vols))
        self.strikes = [p[0] for p in points]
        self.vols = [p[1] for p in points]
        
        self.spline = CubicSpline(self.strikes, self.vols, bc_type='natural')
        
    def get_vol(self, K):
        # Extrapolation could be dangerous with spline, but for this demo let's allow it or clamp
        if K < self.strikes[0]:
            return self.vols[0] # Flat extrap
        if K > self.strikes[-1]:
            return self.vols[-1]
        return float(self.spline(K))
