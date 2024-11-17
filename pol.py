import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
from datetime import datetime
import time

def fetch_stock_data(symbol, api_key, start_date, end_date):
    """Fetch stock data from Polygon.io API"""
    url = f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/day/{start_date}/{end_date}?adjusted=true&sort=asc&apiKey={api_key}"
    
    response = requests.get(url)
    data = response.json()
    
    if "results" not in data:
        st.error(f"Error fetching data for {symbol}: {data.get('error', 'Unknown error')}")
        return None
        
    return data

def process_stock_data(data):
    """Convert Polygon.io data to DataFrame"""
    results = data['results']
    
    df = pd.DataFrame(results)
    df = df.rename(columns={
        'c': 'close',
        'v': 'volume',
        't': 'date',
        'o': 'open',
        'h': 'high',
        'l': 'low',
        'vw': 'vwap'
    })
    
    # Convert timestamp (milliseconds) to datetime
    df['date'] = pd.to_datetime(df['date'], unit='ms')
    df = df.set_index('date')
    
    return df.sort_index()

def calculate_portfolio_performance(stock_data_dict, weights):
    """Calculate weighted portfolio performance"""
    normalized_dfs = {}
    for symbol, df in stock_data_dict.items():
        normalized_df = df.copy()
        normalized_df['close'] = (df['close'] / df['close'].iloc[0]) * 100
        normalized_dfs[symbol] = normalized_df

    common_dates = None
    for df in normalized_dfs.values():
        if common_dates is None:
            common_dates = set(df.index)
        else:
            common_dates = common_dates.intersection(set(df.index))
    
    common_dates = sorted(list(common_dates))
    
    portfolio_values = []
    for date in common_dates:
        value = 0
        for symbol, weight in weights.items():
            value += normalized_dfs[symbol].loc[date, 'close'] * (weight / 100)
        portfolio_values.append({'date': date, 'value': value})

    return pd.DataFrame(portfolio_values).set_index('date')

def calculate_combined_volume(stock_data_dict, weights):
    """Calculate weighted volume performance, normalized to 100"""
    normalized_dfs = {}
    for symbol, df in stock_data_dict.items():
        normalized_df = df.copy()
        normalized_df['volume'] = (df['volume'] / df['volume'].iloc[0]) * 100
        normalized_dfs[symbol] = normalized_df

    common_dates = None
    for df in normalized_dfs.values():
        if common_dates is None:
            common_dates = set(df.index)
        else:
            common_dates = common_dates.intersection(set(df.index))
    
    common_dates = sorted(list(common_dates))
    
    portfolio_volumes = []
    for date in common_dates:
        weighted_volume = 0
        for symbol, weight in weights.items():
            weighted_volume += normalized_dfs[symbol].loc[date, 'volume'] * (weight / 100)
        portfolio_volumes.append({'date': date, 'volume': weighted_volume})

    return pd.DataFrame(portfolio_volumes).set_index('date')

def display_synchronized_charts(stock_data_dict, weights, portfolio_df):
    """Display price and volume charts with synchronized hover effects and matching x-axes"""
    st.markdown("""
    <style>
        .stPlotlyChart {
            height: 400px;
        }
    </style>
    """, unsafe_allow_html=True)

    # Calculate combined volume
    combined_volume_df = calculate_combined_volume(stock_data_dict, weights)
    
    # Find the complete date range
    all_dates = sorted(portfolio_df.index)
    x_range = [all_dates[0], all_dates[-1]]
    
    # Create price chart
    price_fig = go.Figure()
    
    # Add individual stock lines
    for symbol, df in stock_data_dict.items():
        normalized_prices = (df['close'] / df['close'].iloc[0]) * 100
        price_fig.add_trace(go.Scatter(
            x=df.index,
            y=normalized_prices,
            name=f"{symbol} ({weights[symbol]}%)",
            line=dict(dash='dash'),
            customdata=df[['close', 'vwap']],
            hovertemplate="<br>".join([
                "Date: %{x}",
                "Normalized: %{y:.2f}",
                "Price: $%{customdata[0]:.2f}",
                "VWAP: $%{customdata[1]:.2f}"
            ])
        ))

    # Add portfolio line
    price_fig.add_trace(go.Scatter(
        x=portfolio_df.index,
        y=portfolio_df['value'],
        name="Portfolio",
        line=dict(width=3)
    ))

    # Create volume chart
    volume_fig = go.Figure()
    
    # Add individual stock volumes
    for symbol, df in stock_data_dict.items():
        normalized_volume = (df['volume'] / df['volume'].iloc[0]) * 100
        volume_fig.add_trace(go.Scatter(
            x=df.index,
            y=normalized_volume,
            name=f"{symbol} ({weights[symbol]}%)",
            line=dict(dash='dash'),
            opacity=0.7,
            customdata=df['volume'],
            hovertemplate="<br>".join([
                "Date: %{x}",
                "Normalized: %{y:.2f}",
                "Volume: %{customdata:,.0f}"
            ])
        ))
    
    # Add combined volume line
    volume_fig.add_trace(go.Scatter(
        x=combined_volume_df.index,
        y=combined_volume_df['volume'],
        name="Combined Volume",
        line=dict(width=3)
    ))

    # Common layout settings for both charts
    common_layout = dict(
        template="plotly_white",
        height=400,
        showlegend=True,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01
        ),
        hovermode="x unified",
        xaxis=dict(
            range=x_range,
            showspikes=True,
            spikemode='across',
            spikesnap='cursor',
            showline=True,
            showgrid=True,
            rangeslider=dict(visible=False),
            type='date'
        ),
        hoverdistance=1,
        dragmode='zoom',
        spikedistance=1000
    )

    # Update price chart layout
    price_fig.update_layout(
        title="Portfolio Price Performance (Normalized to 100)",
        yaxis_title="Value",
        xaxis_title="",  # Remove x-axis title from top chart
        **common_layout
    )

    # Update volume chart layout
    volume_fig.update_layout(
        title="Trading Volume (Normalized to 100)",
        yaxis_title="Volume Index",
        xaxis_title="Date",
        **common_layout
    )

    # Create containers and display charts
    col1, col2 = st.columns([1, 15])  # This creates space for y-axis labels
    with col2:
        st.plotly_chart(price_fig, use_container_width=True, key="price")
        st.plotly_chart(volume_fig, use_container_width=True, key="volume")

    # Add JavaScript for synchronized zooming and panning
    # Add JavaScript for enhanced synchronization
    st.markdown("""
    <script>
        function waitForCharts(callback) {
            const interval = setInterval(() => {
                const charts = document.querySelectorAll('[data-testid="stPlotlyChart"] .js-plotly-plot');
                if (charts.length >= 2) {
                    clearInterval(interval);
                    callback(charts[0], charts[1]);
                }
            }, 100);
        }

        waitForCharts((priceChart, volumeChart) => {
            if (!priceChart || !volumeChart) return;

            function synchronizeHover(eventData) {
                const xValue = eventData.xvals[0];
                
                // Find nearest points on both charts
                const priceData = priceChart.data;
                const volumeData = volumeChart.data;
                
                // Create hover data for both charts
                const priceHoverData = priceData.map((_, i) => ({
                    curveNumber: i,
                    pointNumber: findNearestPoint(priceData[i].x, xValue)
                }));
                
                const volumeHoverData = volumeData.map((_, i) => ({
                    curveNumber: i,
                    pointNumber: findNearestPoint(volumeData[i].x, xValue)
                }));

                // Trigger hover on both charts
                Plotly.Fx.hover(priceChart, priceHoverData);
                Plotly.Fx.hover(volumeChart, volumeHoverData);
            }

            function findNearestPoint(xArray, target) {
                if (!xArray || !xArray.length) return 0;
                
                let nearest = 0;
                let minDiff = Math.abs(new Date(xArray[0]) - new Date(target));
                
                for (let i = 1; i < xArray.length; i++) {
                    const diff = Math.abs(new Date(xArray[i]) - new Date(target));
                    if (diff < minDiff) {
                        minDiff = diff;
                        nearest = i;
                    }
                }
                return nearest;
            }

            // Add mouse move event listener to container
            const container = document.querySelector('.stPlotlyChart');
            container.addEventListener('mousemove', (e) => {
                const rect = priceChart.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;
                
                if (x >= 0 && x <= rect.width && y >= 0 && y <= rect.height) {
                    const xaxis = priceChart._fullLayout.xaxis;
                    const xValue = xaxis.p2d(x);
                    
                    synchronizeHover({ xvals: [xValue] });
                }
            });

            // Sync zoom and pan events
            priceChart.on('plotly_relayout', (eventdata) => {
                if (eventdata['xaxis.range[0]']) {
                    const update = {
                        'xaxis.range[0]': eventdata['xaxis.range[0]'],
                        'xaxis.range[1]': eventdata['xaxis.range[1]']
                    };
                    Plotly.relayout(volumeChart, update);
                }
            });

            volumeChart.on('plotly_relayout', (eventdata) => {
                if (eventdata['xaxis.range[0]']) {
                    const update = {
                        'xaxis.range[0]': eventdata['xaxis.range[0]'],
                        'xaxis.range[1]': eventdata['xaxis.range[1]']
                    };
                    Plotly.relayout(priceChart, update);
                }
            });

            // Handle mouse leave
            container.addEventListener('mouseleave', () => {
                Plotly.Fx.unhover(priceChart);
                Plotly.Fx.unhover(volumeChart);
            });
        });
    </script>
    """, unsafe_allow_html=True)

    # Display statistics
    st.subheader("Trading Statistics")
    
    stats_data = []
    for symbol, df in stock_data_dict.items():
        latest_close = df['close'].iloc[-1]
        latest_vwap = df['vwap'].iloc[-1]
        price_change = ((df['close'].iloc[-1] / df['close'].iloc[0]) - 1) * 100
        avg_volume = df['volume'].mean()
        
        stats_data.append({
            'Symbol': symbol,
            'Latest Close': f"${latest_close:.2f}",
            'VWAP': f"${latest_vwap:.2f}",
            'Price Change': f"{price_change:+.2f}%",
            'Avg Volume': f"{int(avg_volume):,}",
            'Weight': f"{weights[symbol]}%"
        })
    
    stats_df = pd.DataFrame(stats_data)
    st.table(stats_df.set_index('Symbol'))

def main():
    st.set_page_config(layout="wide", page_title="Portfolio Analyzer")
    
    st.title("Portfolio Analysis Dashboard")
    
    # Add API key input
    api_key = st.sidebar.text_input("Enter Polygon.io API Key:", type="password")
    if not api_key:
        st.warning("Please enter your Polygon.io API key to proceed.")
        return

    # Portfolio configuration section
    st.sidebar.header("Portfolio Configuration")
    
    # Available stocks
    available_stocks = ["AAPL", "GOOGL", "MSFT", "IBM", "AMZN", "TSLA", "META", "NVDA", "JPM", "V"]
    
    # Initialize session state for stocks if not exists
    if 'stocks' not in st.session_state:
        st.session_state.stocks = []

    # Add stock button
    if st.sidebar.button("Add Stock") and len(st.session_state.stocks) < 5:
        st.session_state.stocks.append({"symbol": "", "weight": 0})

    # Dictionary to store stock data
    stock_data_dict = {}
    weights = {}
    
    # Stock selection and weight input
    total_weight = 0
    stocks_to_remove = []

    for idx, stock in enumerate(st.session_state.stocks):
        col1, col2, col3 = st.sidebar.columns([2, 1, 1])
        
        with col1:
            symbol = st.selectbox(
                f"Stock {idx + 1}",
                options=[""] + available_stocks,
                key=f"symbol_{idx}"
            )
            stock["symbol"] = symbol

        with col2:
            weight = st.number_input(
                f"Weight %",
                min_value=0,
                max_value=100,
                value=stock["weight"],
                key=f"weight_{idx}"
            )
            stock["weight"] = weight
            total_weight += weight

        with col3:
            if st.button("Remove", key=f"remove_{idx}"):
                stocks_to_remove.append(idx)

    # Remove marked stocks
    for idx in reversed(stocks_to_remove):
        st.session_state.stocks.pop(idx)

    # Weight validation
    if total_weight != 100:
        st.sidebar.warning(f"Total weight: {total_weight}% (should be 100%)")

    # Add date range selection
    st.sidebar.header("Date Range")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("Start Date", value=pd.Timestamp.now() - pd.Timedelta(days=30))
    with col2:
        end_date = st.date_input("End Date", value=pd.Timestamp.now())

    # Format dates for API
    start_date_str = start_date.strftime('%Y-%m-%d')
    end_date_str = end_date.strftime('%Y-%m-%d')

    # Fetch and process data for selected stocks
    if st.sidebar.button("Analyze Portfolio") and total_weight == 100:
        with st.spinner("Fetching stock data..."):
            for stock in st.session_state.stocks:
                symbol = stock["symbol"]
                if symbol:
                    data = fetch_stock_data(symbol, api_key, start_date_str, end_date_str)
                    if data is not None:
                        stock_data_dict[symbol] = process_stock_data(data)
                        weights[symbol] = stock["weight"]

            if stock_data_dict:
                # Calculate portfolio performance
                portfolio_df = calculate_portfolio_performance(stock_data_dict, weights)
                
                # Display synchronized charts
                display_synchronized_charts(stock_data_dict, weights, portfolio_df)

if __name__ == "__main__":
    main()