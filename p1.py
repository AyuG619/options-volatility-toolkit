# -*- coding: utf-8 -*-
"""P1.ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1tDtCEuckuZ4JGxgOmwQZHBIh1Eyzjn0t
"""

!pip install yfinance

import yfinance as yf
import pandas as pd
import numpy as np
from scipy.stats import norm
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
import warnings
warnings.filterwarnings('ignore')
from scipy.interpolate import griddata, RBFInterpolator
from scipy.interpolate import interp2d

"""PART-1:USING THE NEWTON RAPHSON METHOD ON THE BLACK SCHOLES MODEL TO CALCULATE IMPLIED VOLATILITY FROM USER INPUT"""

#BLACK-SCHOLES MODEL
def bs_price(option_type, S, K, r, t, sigma):

    d1 = (log(S/K) + (r + sigma**2/2)*t)/(sigma*sqrt(t))
    d2 = d1 - sigma*sqrt(t)

    if option_type == 'c':
        return N(d1) * S - N(d2) * K * exp(-r*t)
    elif option_type == 'p':
        return N(-d2) * K * exp(-r*t) - N(-d1) * S
    else:
        return "Please specify call or put options."

#BLACK-SCHOLES MODEL
ONE_CENT = 0.01
#taking input
option_type = (input("call or put option,c for call and p for put: "))
S = float(input("current stock price: "))
K = float(input("strike price: "))
r = float(input("risk-free rate: "))
t = float(eval(input("time to maturity: ")))

MAX_TRY = 1000
market_price = float(input("Enter the market price of the option: "))

def find_iv_newton(option_type, S, K, r, t, market_price):
    _sigma = float(input("Enter the initial sigma: "))

    N = scipy.stats.norm.cdf
    N_prime = scipy.stats.norm.pdf
    for i in range(MAX_TRY):

        d1 = (log(S/K) + (r + _sigma**2/2)*t)/(_sigma*sqrt(t))
        # d2 = d1 - _sigma*sqrt(t) # d2 is not directly used in the vega calculation here

        _bs_price = bs_price(option_type, S, K, r, t, sigma=_sigma)
        diff = market_price - _bs_price
        vega = S * N_prime(d1) * sqrt(t)


        if vega < 1e-9:
             _sigma += diff * 100
        else:
             _sigma += diff/vega

        if abs(diff) < ONE_CENT:
            return _sigma

    return _sigma # Return the last estimated sigma if convergence is not met

print("Implied volatility: ",find_iv_newton(option_type, S, K, r, t, market_price))

"""PART-2:PLOTTING THE VOLATILITY SURFACE"""

r = float(input("risk free rate: "))

# Get stock data
ticker = input("ticker: ")
stock = yf.Ticker(ticker)
spot_price = stock.history(period="1d")["Close"].iloc[-1]
exp_dates = stock.options
selected_expirations = exp_dates[:4]  # Get more expirations for better surface

print(f"Current {ticker} price: ${spot_price:.2f}")

def black_scholes_price(option_type, S, K, r, t, sigma):
    if sigma <= 0 or t <= 0 or S <= 0 or K <= 0:
        return np.nan

    d1 = (np.log(S/K) + (r + 0.5*sigma**2)*t) / (sigma*np.sqrt(t))
    d2 = d1 - sigma*np.sqrt(t)

    if option_type == 'call':
        price = S*norm.cdf(d1) - K*np.exp(-r*t)*norm.cdf(d2)
    else:  # put
        price = K*np.exp(-r*t)*norm.cdf(-d2) - S*norm.cdf(-d1)
    return price

def iv_newton(option_type, S, K, r, t, market_price, max_iter=100, tol=1e-6):
    # Better initial guess based on moneyness and time
    moneyness = S / K if option_type == 'call' else K / S
    if moneyness > 1.1:  # Deep ITM
        sigma = 0.15
    elif moneyness < 0.9:  # Deep OTM
        sigma = 0.4
    else:  # ATM
        sigma = 0.25

    # Additional guess based on time to expiration
    if t < 0.08:  # Less than 1 month
        sigma *= 1.5

    for i in range(max_iter):
        price = black_scholes_price(option_type, S, K, r, t, sigma)
        if np.isnan(price):
            return np.nan

        # Calculate vega with current sigma
        d1 = (np.log(S/K) + (r + 0.5*sigma**2)*t) / (sigma*np.sqrt(t))
        vega = S * norm.pdf(d1) * np.sqrt(t)

        if vega < 1e-8:
            return np.nan

        diff = market_price - price
        if abs(diff) < tol:
            return sigma

        sigma_new = sigma + diff/vega

        # Strict bounds for realistic volatilities
        sigma_new = max(0.05, min(sigma_new, 2.0))

        if abs(sigma_new - sigma) < tol:
            return sigma_new

        sigma = sigma_new

    return sigma if 0.05 <= sigma <= 2.0 else np.nan

# Fetch and filter options data more strictly
option_chains = []
for expiry in selected_expirations:
    try:
        opt_chain = stock.option_chain(expiry)

        # Process calls
        calls = opt_chain.calls.copy()
        calls['option_type'] = 'call'
        calls['expiry'] = expiry

        # Process puts
        puts = opt_chain.puts.copy()
        puts['option_type'] = 'put'
        puts['expiry'] = expiry

        option_chains.extend([calls, puts])
    except:
        continue

df = pd.concat(option_chains, ignore_index=True)

# Calculate time to expiration
df['t'] = (pd.to_datetime(df['expiry']) - pd.Timestamp.now()).dt.days / 365.25


print("Applying strict filters")

# 1. Time filter: At least 7 days, max 1 year
df = df[(df['t'] >= 0.02) & (df['t'] <= 1.0)]

# 2. Moneyness filter: Only options reasonably close to ATM
df['moneyness'] = df['strike'] / spot_price
df = df[(df['moneyness'] >= 0.7) & (df['moneyness'] <= 1.3)]

# 3. Volume filter: Must have recent trading activity
df = df[df['volume'] >= 5]

# 4. Open interest filter: Must have some open interest
df = df[df['openInterest'] >= 10]

# 5. Bid-ask spread filter: Remove wide spreads
df['spread'] = df['ask'] - df['bid']
df['mid_price'] = (df['bid'] + df['ask']) / 2
df = df[(df['spread'] > 0) & (df['spread'] <= df['mid_price'] * 0.3)]

# 6. Price sanity check
df = df[df['mid_price'] >= 0.05]

# 7. Remove options where bid is zero (likely stale)
df = df[df['bid'] > 0]

print(f"Options after strict filtering: {len(df)}")

if len(df) < 20:
    print("Warning: Very few options passed filtering. Consider relaxing filters.")

# Calculate IV using mid price
df['market_price'] = df['mid_price']
df['impliedVolatility'] = df.apply(
    lambda row: iv_newton(
        option_type=row['option_type'],
        S=spot_price,
        K=row['strike'],
        r=r,
        t=row['t'],
        market_price=row['market_price']
    ),
    axis=1
)

# Final IV filtering
df = df.dropna(subset=['impliedVolatility'])
df = df[(df['impliedVolatility'] >= 0.05) & (df['impliedVolatility'] <= 1.0)]

print(f"Options with valid IV: {len(df)}")

# Additional smoothing: Remove obvious outliers
iv_median = df['impliedVolatility'].median()
iv_mad = np.median(np.abs(df['impliedVolatility'] - iv_median))
threshold = iv_median + 3 * iv_mad
df = df[df['impliedVolatility'] <= threshold]

print(f"Options after outlier removal: {len(df)}")

# Create improved volatility surface
if len(df) >= 15:
    # Method 1: Interpolated Surface using griddata
    fig = plt.figure(figsize=(15, 12))

    # Create subplot for surface plot
    ax1 = fig.add_subplot(221, projection='3d')

    # Prepare data
    strikes = df['strike'].values
    times = df['t'].values
    ivs = df['impliedVolatility'].values

    # Create regular grid for interpolation
    strike_min, strike_max = strikes.min(), strikes.max()
    time_min, time_max = times.min(), times.max()

    # Create denser grid
    strike_grid = np.linspace(strike_min, strike_max, 30)
    time_grid = np.linspace(time_min, time_max, 20)
    Strike_mesh, Time_mesh = np.meshgrid(strike_grid, time_grid)

    # Interpolate volatilities onto regular grid
    points = np.column_stack((strikes, times))
    IV_mesh = griddata(points, ivs, (Strike_mesh, Time_mesh), method='cubic', fill_value=np.nan)

    # Remove NaN values for cleaner surface
    mask = ~np.isnan(IV_mesh)

    # Plot surface
    surf = ax1.plot_surface(Strike_mesh, Time_mesh, IV_mesh,
                           cmap='viridis', alpha=0.8, antialiased=True)

    # Overlay original data points
    calls = df[df['option_type'] == 'call']
    puts = df[df['option_type'] == 'put']

    if len(calls) > 0:
        ax1.scatter(calls['strike'], calls['t'], calls['impliedVolatility'],
                   c='red', s=30, alpha=0.8, label='Calls')
    if len(puts) > 0:
        ax1.scatter(puts['strike'], puts['t'], puts['impliedVolatility'],
                   c='blue', s=30, alpha=0.8, label='Puts')

    ax1.set_xlabel('Strike Price')
    ax1.set_ylabel('Time to Expiration (Years)')
    ax1.set_zlabel('Implied Volatility')
    ax1.set_title(f'{ticker} - Interpolated Volatility Surface')
    ax1.legend()

    # Add colorbar
    plt.colorbar(surf, ax=ax1, shrink=0.5)

    # Method 2: Contour plot (2D view)
    ax2 = fig.add_subplot(222)
    contour = ax2.contourf(Strike_mesh, Time_mesh, IV_mesh, levels=15, cmap='viridis')
    ax2.scatter(strikes, times, c=ivs, cmap='viridis', s=20, edgecolors='black', alpha=0.7)
    ax2.set_xlabel('Strike Price')
    ax2.set_ylabel('Time to Expiration (Years)')
    ax2.set_title('Volatility Surface - Contour View')
    plt.colorbar(contour, ax=ax2)

    # Method 3: Alternative using RBF interpolation (often smoother)
    ax3 = fig.add_subplot(223, projection='3d')

    try:
        # RBF interpolation (smoother but can be slower)
        rbf_interp = RBFInterpolator(points, ivs, kernel='thin_plate_spline', smoothing=0.01)
        IV_mesh_rbf = rbf_interp(np.column_stack([Strike_mesh.ravel(), Time_mesh.ravel()]))
        IV_mesh_rbf = IV_mesh_rbf.reshape(Strike_mesh.shape)

        surf_rbf = ax3.plot_surface(Strike_mesh, Time_mesh, IV_mesh_rbf,
                                   cmap='plasma', alpha=0.8, antialiased=True)

        # Overlay data points
        if len(calls) > 0:
            ax3.scatter(calls['strike'], calls['t'], calls['impliedVolatility'],
                       c='red', s=30, alpha=0.8)
        if len(puts) > 0:
            ax3.scatter(puts['strike'], puts['t'], puts['impliedVolatility'],
                       c='blue', s=30, alpha=0.8)

        ax3.set_xlabel('Strike Price')
        ax3.set_ylabel('Time to Expiration (Years)')
        ax3.set_zlabel('Implied Volatility')
        ax3.set_title(f'{ticker} - RBF Interpolated Surface')
        plt.colorbar(surf_rbf, ax=ax3, shrink=0.5)

    except Exception as e:
        ax3.text(0.5, 0.5, 0.5, f'RBF failed: {str(e)}', transform=ax3.transAxes)

    # Method 4: Wireframe with original points
    ax4 = fig.add_subplot(224, projection='3d')
    ax4.plot_wireframe(Strike_mesh, Time_mesh, IV_mesh, alpha=0.6, color='gray')

    # Color-code the original points
    scatter = ax4.scatter(strikes, times, ivs, c=ivs, cmap='viridis', s=50, alpha=0.8)
    ax4.set_xlabel('Strike Price')
    ax4.set_ylabel('Time to Expiration (Years)')
    ax4.set_zlabel('Implied Volatility')
    ax4.set_title('Wireframe + Data Points')
    plt.colorbar(scatter, ax=ax4, shrink=0.5)

    plt.tight_layout()
    plt.show()

    # Print interpolation quality metrics
    print(f"\nSurface Quality Metrics:")
    print(f"Original data points: {len(df)}")
    print(f"Grid resolution: {len(strike_grid)} x {len(time_grid)}")
    print(f"Interpolated points: {np.sum(~np.isnan(IV_mesh))}")
    print(f"Coverage: {np.sum(~np.isnan(IV_mesh))/IV_mesh.size:.1%}")

else:
    print("Insufficient data for volatility surface after filtering")

# Additional function for better surface smoothing
def create_smooth_surface(df, ticker, method='cubic'):
    """
    Create a smooth volatility surface with better interpolation
    """
    if len(df) < 10:
        print("Need at least 10 data points for smooth surface")
        return

    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection='3d')

    # Prepare data
    strikes = df['strike'].values
    times = df['t'].values
    ivs = df['impliedVolatility'].values

    # Create finer grid
    strike_range = strikes.max() - strikes.min()
    time_range = times.max() - times.min()

    # Extend grid slightly beyond data range
    strike_grid = np.linspace(strikes.min() - 0.05*strike_range,
                             strikes.max() + 0.05*strike_range, 40)
    time_grid = np.linspace(max(times.min() - 0.02*time_range, 0.01),
                           times.max() + 0.02*time_range, 25)

    Strike_mesh, Time_mesh = np.meshgrid(strike_grid, time_grid)

    # Multiple interpolation methods for robustness
    points = np.column_stack((strikes, times))

    try:
        # Primary interpolation
        IV_mesh = griddata(points, ivs, (Strike_mesh, Time_mesh),
                          method=method, fill_value=np.nan)

        # Fill holes with linear interpolation
        mask_nan = np.isnan(IV_mesh)
        if np.any(mask_nan):
            IV_mesh_linear = griddata(points, ivs, (Strike_mesh, Time_mesh),
                                    method='linear', fill_value=np.nan)
            IV_mesh[mask_nan] = IV_mesh_linear[mask_nan]

        # Smooth the surface
        from scipy.ndimage import gaussian_filter
        IV_mesh_smooth = gaussian_filter(IV_mesh, sigma=0.8, mode='nearest')

        # Plot surface
        surf = ax.plot_surface(Strike_mesh, Time_mesh, IV_mesh_smooth,
                              cmap='viridis', alpha=0.9, antialiased=True,
                              linewidth=0, rasterized=True)

        # Add original data points
        scatter = ax.scatter(strikes, times, ivs, c='red', s=40, alpha=0.8,
                           edgecolors='darkred', linewidth=1)

        ax.set_xlabel('Strike Price ($)')
        ax.set_ylabel('Time to Expiration (Years)')
        ax.set_zlabel('Implied Volatility')
        ax.set_title(f'{ticker} - Smooth Volatility Surface ({method} interpolation)')

        # Improve viewing angle
        ax.view_init(elev=25, azim=45)

        # Add colorbar
        plt.colorbar(surf, ax=ax, shrink=0.6, aspect=20)

        plt.tight_layout()
        plt.show()

        return IV_mesh_smooth, Strike_mesh, Time_mesh

    except Exception as e:
        print(f"Surface creation failed: {e}")
        return None, None, None

# Use the function
surface_data = create_smooth_surface(df, ticker, method='cubic')

"""PART-3:BLACK SCHOLES GREEKS

"""

!pip install sympy
from sympy import symbols, diff

#option greeks.

def delta(option_type, S, K, r, t, sigma):

  d1 = (np.log(S/K) + (r + 0.5*sigma**2)*t) / (sigma*np.sqrt(t))
  d2 = d1 - sigma*np.sqrt(t)
  if option_type == 'call':
    delta_= norm.cdf(d1)
  else:  # put
    delta_= -norm.cdf(-d1)
  return delta_

def gamma(option_type, S, K, r, t, sigma):
  d1 = (np.log(S/K) + (r + 0.5*sigma**2)*t) / (sigma*np.sqrt(t))
  d2 = d1 - sigma*np.sqrt(t)
  gamma_= norm.pdf(d1) / (S*sigma*np.sqrt(t))

  return gamma_


def theta(option_type, S, K, r, t, sigma):
  d1 = (np.log(S/K) + (r + 0.5*sigma**2)*t) / (sigma*np.sqrt(t))
  d2 = d1 - sigma*np.sqrt(t)
  if option_type == 'call':
    theta_= -S*norm.pdf(d1)*sigma/(2*np.sqrt(t)) - r*K*np.exp(-r*t)*norm.cdf(d2)
  else:  # put
    theta_= -S*norm.pdf(d1)*sigma/(2*np.sqrt(t)) + r*K*np.exp(-r*t)*norm.cdf(-d2)
    theta_= theta_/365 # Theta is typically quoted per day
  return theta_

def vega(option_type, S, K, r, t, sigma):
  d1 = (np.log(S/K) + (r + 0.5*sigma**2)*t) / (sigma*np.sqrt(t))
  # d2 is not needed for vega calculation
  vega_= S*norm.pdf(d1)*np.sqrt(t)

  vega_ = vega_ * 0.01
  return vega_

def rho(option_type, S, K, r, t, sigma):
  d1 = (np.log(S/K) + (r + 0.5*sigma**2)*t) / (sigma*np.sqrt(t))
  d2 = d1 - sigma*np.sqrt(t)
  if option_type == 'call':
    rho_= K*t*np.exp(-r*t)*norm.cdf(d2)
  else:  # put
    rho_= -K*t*np.exp(-r*t)*norm.cdf(-d2)

  rho_ = rho_ * 0.01 # Add this line if you want rho for 1% change
  return rho_

option_chains = []
for expiry in selected_expirations:
    try:
        opt_chain = stock.option_chain(expiry)

        # Process calls
        calls = opt_chain.calls.copy()
        calls['option_type'] = 'call'
        calls['expiry'] = expiry

        # Process puts
        puts = opt_chain.puts.copy()
        puts['option_type'] = 'put'
        puts['expiry'] = expiry

        option_chains.extend([calls, puts])
    except:
        continue

df = pd.concat(option_chains, ignore_index=True)

# Calculate time to expiration
df['t'] = (pd.to_datetime(df['expiry']) - pd.Timestamp.now()).dt.days / 365.25

# Calculate mid_price as it's needed for IV calculation
df['mid_price'] = (df['bid'] + df['ask']) / 2

# Calculate implied volatility first using mid_price
df['impliedVolatility'] = df.apply(
    lambda row: iv_newton(
        option_type=row['option_type'],
        S=spot_price,
        K=row['strike'],
        r=r,
        t=row['t'],
        market_price=row['mid_price'] # Use mid_price as market price for IV calculation
    ),
    axis=1
)

# Drop rows where IV could not be calculated
df = df.dropna(subset=['impliedVolatility'])

# Filter for reasonable IV values before calculating Greeks
df = df[(df['impliedVolatility'] >= 0.05) & (df['impliedVolatility'] <= 2.0)] # Added an upper bound for IV

print(f"Options with valid IV for Greeks calculation: {len(df)}")


# Now calculate Greeks using the calculated implied volatility (sigma)
df['delta'] = df.apply(
    lambda row: delta(
        option_type=row['option_type'],
        S=spot_price,
        K=row['strike'],
        r=r,
        t=row['t'],
        sigma=row['impliedVolatility'] # Pass the calculated IV as sigma
    ),
    axis=1
)
df['gamma'] = df.apply(
    lambda row: gamma(
        option_type=row['option_type'],
        S=spot_price,
        K=row['strike'],
        r=r,
        t=row['t'],
        sigma=row['impliedVolatility'] # Pass the calculated IV as sigma
    ),
    axis=1
)
df['vega'] = df.apply(
    lambda row: vega(
        option_type=row['option_type'],
        S=spot_price,
        K=row['strike'],
        r=r,
        t=row['t'],
        sigma=row['impliedVolatility'] # Pass the calculated IV as sigma
    ),
    axis=1
)
df['rho'] = df.apply(
    lambda row: rho(
        option_type=row['option_type'],
        S=spot_price,
        K=row['strike'],
        r=r,
        t=row['t'],
        sigma=row['impliedVolatility'] # Pass the calculated IV as sigma
    ),
    axis=1
)
df['theta'] = df.apply(
    lambda row: theta(
        option_type=row['option_type'],
        S=spot_price,
        K=row['strike'],
        r=r,
        t=row['t'],
        sigma=row['impliedVolatility'] # Pass the calculated IV as sigma
    ),
    axis=1
)

# Display the DataFrame with Greeks
print(df[['contractSymbol', 'strike', 't', 'option_type', 'mid_price', 'impliedVolatility', 'delta', 'gamma', 'vega', 'theta', 'rho']].head())