
import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from pricing import VanillaFxOptionPricer, VolatilitySurface

class FxPricerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("FX Option Pricer (Standalone)")
        self.geometry("1400x800")
        
        # Configure Grid
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        
        # Main Container
        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")
        
        # Columns
        # We will use 2 main columns: Inputs (Left) and Outputs (Right)
        # Inputs will have Market Data and Contract Details
        # Outputs will have Results and Charts
        
        left_pane = ttk.Frame(main_frame)
        left_pane.grid(row=0, column=0, sticky="nsew", padx=5)
        
        right_pane = ttk.Frame(main_frame)
        right_pane.grid(row=0, column=1, sticky="nsew", padx=5)
        
        main_frame.columnconfigure(1, weight=3) # Give more space to charts
        
        # --- Market Data Section ---
        market_frame = ttk.LabelFrame(left_pane, text="Market Data", padding="10")
        market_frame.pack(fill="x", pady=5)
        
        self.entries = {}
        
        self.add_entry(market_frame, "Spot Reference", "spot_ref", "1.0")
        self.add_entry(market_frame, "Domestic Rate (rd)", "rd", "0.05")
        self.add_entry(market_frame, "Forward Rate (F)", "forward", "1.051")
        self.add_entry(market_frame, "ATM Vol", "atm", "0.10")
        
        # Surface Rows
        row1 = ttk.Frame(market_frame)
        row1.pack(fill="x")
        self.add_entry(row1, "25d RR", "rr25", "0.01", side="left", width=10)
        self.add_entry(row1, "25d ST", "st25", "0.002", side="left", width=10)
        
        row2 = ttk.Frame(market_frame)
        row2.pack(fill="x")
        self.add_entry(row2, "10d RR", "rr10", "0.015", side="left", width=10)
        self.add_entry(row2, "10d ST", "st10", "0.005", side="left", width=10)
        
        # --- Contract Details Section ---
        contract_frame = ttk.LabelFrame(left_pane, text="Contract Details", padding="10")
        contract_frame.pack(fill="x", pady=5)
        
        self.add_entry(contract_frame, "Maturity (Years)", "T", "1.0")
        
        # Strike Type and Value
        st_frame = ttk.Frame(contract_frame)
        st_frame.pack(fill="x", pady=5)
        ttk.Label(st_frame, text="Strike Type:").pack(anchor="w")
        self.strike_type_var = tk.StringVar(value="price")
        combo_st = ttk.Combobox(st_frame, textvariable=self.strike_type_var, values=["price", "delta"], state="readonly")
        combo_st.pack(fill="x")
        combo_st.bind("<<ComboboxSelected>>", self.update_ui_state)
        
        self.add_entry(contract_frame, "Strike / Delta", "strike", "1.0")
        
        # Strike 2 (Hidden by default logic)
        self.strike2_frame = ttk.Frame(contract_frame)
        self.strike2_frame.pack(fill="x")
        self.add_entry(self.strike2_frame, "Call Strike (Strangle/RR)", "strike_2", "1.05")
        
        # Option Type
        ttk.Label(contract_frame, text="Type").pack(anchor="w")
        self.type_var = tk.StringVar(value="call")
        combo_type = ttk.Combobox(contract_frame, textvariable=self.type_var, values=["call", "put", "strangle", "risk_reversal"], state="readonly")
        combo_type.pack(fill="x")
        combo_type.bind("<<ComboboxSelected>>", self.update_ui_state)
        
        # Calculate Button
        calc_btn = ttk.Button(left_pane, text="Price Option", command=self.calculate)
        calc_btn.pack(fill="x", pady=20)
        
        # --- Results Section ---
        results_frame = ttk.LabelFrame(left_pane, text="Results", padding="10")
        results_frame.pack(fill="x", pady=5)
        
        self.results = {}
        for key in ["Price", "IV Used", "Strike Used", "BS Vega"]:
            f = ttk.Frame(results_frame)
            f.pack(fill="x", pady=2)
            ttk.Label(f, text=key).pack(side="left")
            val_lbl = ttk.Label(f, text="--", font=("Helvetica", 12, "bold"))
            val_lbl.pack(side="right")
            self.results[key] = val_lbl
            
        # Model Vega
        ttk.Label(results_frame, text="Model Sensitivities:", font=("Helvetica", 10, "italic")).pack(anchor="w", pady=(10,0))
        self.model_vega_lbl = ttk.Label(results_frame, text="--", foreground="#555")
        self.model_vega_lbl.pack(anchor="w")

        # --- Charts Section ---
        charts_frame = ttk.LabelFrame(right_pane, text="Charts", padding="10")
        charts_frame.pack(fill="both", expand=True)
        
        # Figure
        self.fig = plt.Figure(figsize=(8, 8), dpi=100)
        self.ax_vol = self.fig.add_subplot(211)
        self.ax_payoff = self.fig.add_subplot(212)
        self.fig.tight_layout(pad=4.0)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=charts_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        
        self.update_ui_state()

    def add_entry(self, parent, label, key, default, side=None, width=None):
        if side:
            f = ttk.Frame(parent)
            f.pack(side=side, padx=5, fill="x", expand=True)
            ttk.Label(f, text=label).pack(anchor="w")
            e = ttk.Entry(f, width=width)
            e.insert(0, default)
            e.pack(fill="x")
            self.entries[key] = e
        else:
            ttk.Label(parent, text=label).pack(anchor="w")
            e = ttk.Entry(parent)
            e.insert(0, default)
            e.pack(fill="x", pady=(0, 5))
            self.entries[key] = e
            
    def update_ui_state(self, event=None):
        opt_type = self.type_var.get()
        strike_type = self.strike_type_var.get()
        
        is_multi_leg = opt_type in ['strangle', 'risk_reversal']
        is_delta = strike_type == 'delta'
        
        # Show/Hide Strike 2
        # Visible only if multi-leg AND price mode
        # OR if multi-leg AND delta (but usually delta RR is symmetric single input? App logic says yes)
        # Actually in app.py logic handle delta strangle/RR as single delta input.
        # So Strike 2 is only needed if Strike Type is PRICE and it is MULTI LEG. (Or specifically handled).
        # Let's match script.js logic:
        # if (isDelta) strike2Group add hidden
        # else if (isMultiLeg) strike2Group remove hidden
        
        if is_delta:
            self.pack_forget_widget(self.strike2_frame)
        elif is_multi_leg:
             self.strike2_frame.pack(fill="x", after=self.entries['strike'])
        else:
            self.pack_forget_widget(self.strike2_frame)
            
    def pack_forget_widget(self, widget):
        try:
            widget.pack_forget()
        except:
            pass

    def get_float(self, key):
        return float(self.entries[key].get())

    def calculate(self):
        try:
            # Gather Data
            spot = self.get_float('spot_ref')
            rd = self.get_float('rd')
            fwd = self.get_float('forward')
            T = self.get_float('T')
            
            atm = self.get_float('atm')
            rr25 = self.get_float('rr25')
            st25 = self.get_float('st25')
            rr10 = self.get_float('rr10')
            st10 = self.get_float('st10')
            
            strike_input = self.get_float('strike')
            strike_2_input = self.get_float('strike_2')
            
            opt_type = self.type_var.get()
            strike_type = self.strike_type_var.get()
            
            # Pricing Logic (Copied/Adapted from app.py)
            pricer = VanillaFxOptionPricer(spot, rd, fwd, T)
            surface = VolatilitySurface(atm, rr25, st25, rr10, st10)
            surface.construct_smile(pricer)
            
            strike = 0.0
            strike_Display = ""
            vol_Display = 0.0
            price = 0.0
            
            # --- Resolve Strikes ---
            
            # Defaults
            final_strike_1 = 0
            final_strike_2 = 0
            
            if opt_type == 'risk_reversal':
                if strike_type == 'delta':
                    k_put = pricer.solve_strike_for_delta(strike_input, 'put', surface)
                    k_call = pricer.solve_strike_for_delta(strike_input, 'call', surface)
                    final_strike_1 = k_put
                    final_strike_2 = k_call
                else:
                    final_strike_1 = strike_input
                    final_strike_2 = strike_2_input
                
                vol1 = surface.get_vol(final_strike_1)
                vol2 = surface.get_vol(final_strike_2)
                p1 = pricer.price(vol1, final_strike_1, 'put')
                p2 = pricer.price(vol2, final_strike_2, 'call')
                price = p2 - p1
                vol_Display = (vol1 + vol2) / 2
                strike_Display = f"{final_strike_1:.4f} / {final_strike_2:.4f}"
                
            elif opt_type == 'strangle':
                if strike_type == 'delta':
                    k_put = pricer.solve_strike_for_delta(strike_input, 'put', surface)
                    k_call = pricer.solve_strike_for_delta(strike_input, 'call', surface)
                    final_strike_1 = k_put
                    final_strike_2 = k_call
                else:
                    final_strike_1 = strike_input
                    final_strike_2 = strike_2_input

                vol1 = surface.get_vol(final_strike_1)
                vol2 = surface.get_vol(final_strike_2)
                p1 = pricer.price(vol1, final_strike_1, 'put')
                p2 = pricer.price(vol2, final_strike_2, 'call')
                price = p1 + p2
                vol_Display = (vol1 + vol2) / 2
                strike_Display = f"{final_strike_1:.4f} / {final_strike_2:.4f}"
                
            else: # Call or Put
                if strike_type == 'delta':
                    k = pricer.solve_strike_for_delta(strike_input, opt_type, surface)
                    final_strike_1 = k
                else:
                    final_strike_1 = strike_input
                    
                vol_Display = surface.get_vol(final_strike_1)
                price = pricer.price(vol_Display, final_strike_1, opt_type)
                strike_Display = f"{final_strike_1:.4f}"
                
                # BS Vega for single leg
                vega = pricer.calculate_vega(final_strike_1, vol_Display)
                self.results['BS Vega'].config(text=f"{vega:.4f}")

            # Vega for Multi-leg?
            # app.py logic: "Vega is sum of vegas" for strangle. For RR?
            # RR = Call - Put. Vega = Vega_Call - Vega_Put.
            if opt_type in ['strangle', 'risk_reversal']:
                v1 = pricer.calculate_vega(final_strike_1, surface.get_vol(final_strike_1))
                v2 = pricer.calculate_vega(final_strike_2, surface.get_vol(final_strike_2))
                if opt_type == 'strangle':
                    self.results['BS Vega'].config(text=f"{v1 + v2:.4f}")
                else:
                    self.results['BS Vega'].config(text=f"{v2 - v1:.4f}") # Call - Put
            
            # --- Outputs ---
            self.results['Price'].config(text=f"{price:.6f} {opt_type[0].upper()}") # Unit?
            self.results['IV Used'].config(text=f"{vol_Display:.2%}")
            self.results['Strike Used'].config(text=strike_Display)
            
            # Model Vega (Approximation: just do calculate_model_sensitivities for single leg or skip for complex?)
            # app.py does it for "strike" (first leg usually).
            # Let's simplify and just show "N/A" for multi-leg or calculate for first strike.
            if opt_type in ['call', 'put']:
                sens = pricer.calculate_model_sensitivities(final_strike_1, opt_type, surface)
                sens_text = ", ".join([f"{k}: {v:.2f}" for k, v in sens.items()])
                self.model_vega_lbl.config(text=sens_text)
            else:
                self.model_vega_lbl.config(text="( Sensitivities available for single leg only )")

            # --- Plots ---
            # 1. Vol Surface
            self.ax_vol.clear()
            self.ax_vol.set_title("Volatility Smile")
            self.ax_vol.set_xlabel("Strike")
            self.ax_vol.set_ylabel("Volatility")
            self.ax_vol.grid(True, alpha=0.3)
            
            # Plot Curve
            min_k = final_strike_1 * 0.8 if final_strike_1 > 0 else spot * 0.8
            max_k = final_strike_1 * 1.2 if final_strike_1 > 0 else spot * 1.2
            if opt_type in ['strangle', 'risk_reversal']: # adjust bounds
                 max_k = final_strike_2 * 1.2
                 
            ks = np.linspace(min_k, max_k, 50)
            vols = [surface.get_vol(k) for k in ks]
            self.ax_vol.plot(ks, vols, 'b-', label='Smile')
            
            # Plot Points
            if opt_type in ['strangle', 'risk_reversal']:
                self.ax_vol.plot([final_strike_1, final_strike_2], [surface.get_vol(final_strike_1), surface.get_vol(final_strike_2)], 'ro')
            else:
                self.ax_vol.plot([final_strike_1], [vol_Display], 'ro')
                
            # 2. Payoff Chart
            self.ax_payoff.clear()
            self.ax_payoff.set_title(f"Payoff: {opt_type.replace('_', ' ').title()}")
            self.ax_payoff.set_xlabel("Spot @ Maturity")
            self.ax_payoff.set_ylabel("Value")
            self.ax_payoff.grid(True, alpha=0.3)
            self.ax_payoff.axhline(0, color='black', linewidth=1)
            
            spots = np.linspace(spot * 0.8, spot * 1.2, 100)
            payoffs = []
            for s in spots:
                val = 0
                if opt_type == 'call':
                    val = max(s - final_strike_1, 0)
                elif opt_type == 'put':
                    val = max(final_strike_1 - s, 0)
                elif opt_type == 'strangle': # Long Strangle
                    val = max(final_strike_1 - s, 0) + max(s - final_strike_2, 0)
                elif opt_type == 'risk_reversal': # Call - Put
                    val = max(s - final_strike_2, 0) - max(final_strike_1 - s, 0)
                payoffs.append(val)
                
            self.ax_payoff.fill_between(spots, payoffs, 0, alpha=0.2, color='green')
            self.ax_payoff.plot(spots, payoffs, 'g-')
            
            self.canvas.draw()
            
        except Exception as e:
            messagebox.showerror("Error", str(e))
            raise e

if __name__ == "__main__":
    app = FxPricerApp()
    app.mainloop()
