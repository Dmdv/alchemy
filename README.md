# Alchemist: High-Performance Automated Trading System

## Table of Contents

- [Alchemist: High-Performance Automated Trading System](#alchemist-high-performance-automated-trading-system)
  - [Table of Contents](#table-of-contents)
  - [Links](#links)
  - [What Components Do I Need?](#what-components-do-i-need)
  - [Building My Own Automated Trading Engine](#building-my-own-automated-trading-engine)
    - [Alchemist — The Automated Trading Engine](#alchemist--the-automated-trading-engine)
      - [Example: Deploying a Trading Strategy](#example-deploying-a-trading-strategy)
      - [Example: Creating a Strategy Class](#example-creating-a-strategy-class)
  - [Building My Own Data Pipeline](#building-my-own-data-pipeline)
  - [Using Backtrader to Backtest Strategies](#using-backtrader-to-backtest-strategies)
  - [My Philosophy of Strategy Development](#my-philosophy-of-strategy-development)

---

## Links

- [How I Started My Algorithmic Trading Business](https://wire.insiderfinance.io/how-i-started-my-algorithmic-trading-business-96b344b8c541)
- [Alchemist: A Ray-based High-Performance Automated Trading System (Notion)](https://boulder-submarine-0ae.notion.site/Alchemist-A-Ray-based-High-Performance-Automated-Trading-System-1ace87b87fa4803cb9ade11517148d65)
- [trading-data GitHub](https://github.com/lokhiufung/trading-data)
- [alchemist GitHub](https://github.com/lokhiufung/alchemist)

---

## What Components Do I Need?

When I started to trade seriously, I tried to get some of the most essential components on my hands. I share Jim Simons's view that removing emotion is one of the most important aspects of financial trading. Also, when looking for patterns and backtesting, I need to have a pool of historical data and an engine to load specific data from the pool and run backtests.

To meet my trading requirements, I identified three essential components:

1. **An automated trading engine** — to deploy strategies without manual intervention or emotional bias.
2. **A data pipeline** — to collect and manage historical data for backtesting and strategy analysis.
3. **A backtesting engine** — to test strategies rigorously before live deployment.

---

## Building My Own Automated Trading Engine

For any trading business, the primary focus should be on building strategies that outperform the market. I started by using Backtrader as my automated trading engine. However, I found Backtrader difficult to debug when building strategies — maybe that deserves a separate article.

As a senior quant developer, I feel confident to build my own automated trading engine. I decided to maintain my own automated trading engine. I can ensure that I have full control of the system and the system can fit my requirements.

### Alchemist — The Automated Trading Engine

Alchemist is a high-performance, distributed automated trading system designed to seamlessly transition quantitative research into fully automated algorithmic trading strategies.

Built on Ray, Alchemist provides a scalable infrastructure for strategy execution, real-time order management, and seamless integration with market data and broker connections. Whether you're a quantitative researcher, algorithmic trader, or hedge fund, Alchemist helps you deploy, manage, and scale trading strategies efficiently.

Alchemist bridges what I call the "research-to-execution gap" — the painful leap from a promising backtest to a working live deployment.

#### Example: Deploying a Trading Strategy

Below is a simplified example of how I deploy a trading strategy on Interactive Brokers using Alchemist.

```python
from alchemist.account import Account
from alchemist.data_card import DataCard
from alchemist.products.stock_product import StockProduct
from alchemist.gateways.ib_gateway import  IbGateway

accounts = [
    Account(**account)
]
products = [
    StockProduct(
        name=products[i]['name'],
        base_currency=products[i]['base_currency'],
        exch=products[i]['exch']
    ) for i in range(len(products))
]
data_cards = [
    DataCard(
        product=products[i],
        freq=data_cards[i]['freq'],
        aggregation=data_cards[i]['aggregation']
    ) for i in range(len(data_cards))

]

monitor_actor = TelegramMonitor.remote(
    bot_token=os.getenv('TELEGRAM_BOT_TOKEN'),
    chat_id=os.getenv('TELEGRAM_CHAT_ID'),
    flush_interval=60.0,
    is_test=False,
)
strategy_actor = BBReversalStrategy.remote(
    name=strategy['name'],
    zmq_send_port=strategy['zmq_send_port'],
    zmq_recv_ports=strategy['zmq_recv_ports'],
    products=products,
    data_cards=data_cards,
    data_pipeline='IBDataPipeline',  # REMINDER: this must be a class name. it will be imported inside the actor process
    data_pipeline_kwargs={
        'account': accounts[0],
    },
    monitor_actor=monitor_actor
)
gateway_actor = IbGateway.remote(
    subscriptions=gateway['subscriptions'],
    zmq_send_port=gateway['zmq_send_port'],
    zmq_recv_ports=gateway['zmq_recv_ports'],
    accounts=accounts,
    products=products,
)

# start backfilling
backfill_start_date = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')  # TEMP: fill 2 days of min bar data

ray.get(strategy_actor.start_backfilling.remote(
    backfilling_start_date=backfill_start_date,
))

gateway_actor.start.remote()
strategy_actor.start.remote()

# Passive run loop (could evolve into a monitoring system)
market_close_time = datetime.now().replace(hour=16, minute=0, second=0, microsecond=0)
try:
    while datetime.now() < market_close_time:
        time.sleep(60)
        # optionally poll actor health here
    print("Market close reached. Shutting down strategy and gateway...")
    ray.shutdown()
    sys.exit(0)
except KeyboardInterrupt:
    print("Manual shutdown requested.")
    ray.shutdown()
    sys.exit(0)
```

#### Example: Creating a Strategy Class

To create a strategy, you can write a strategy class with similar style in backtrader:

```python
import typing

import ray

from alchemist.strategies.base_strategy import BaseStrategy
from alchemist.datas.bar_data import BarData
from alchemist.products.base_product import BaseProduct
from alchemist.indicators.sma_indicator import SmaIndicator

@ray.remote
class MovingAverageStrategy(BaseStrategy):
    """
    A benchmark strategy that uses a simple moving average to generate buy/sell signals.
    """
    STRAT = 'strat-baseline-1'
    PARAMS = {
        'period': 10
    }

    def __init__(self, name, zmq_send_port, zmq_recv_ports, products: typing.List[BaseProduct], data_cards, data_pipeline=None, data_pipelin_kwargs=None, max_len=1000, params=None, monitor_actor=None):
        super().__init__(name, zmq_send_port, zmq_recv_ports, products, data_cards, data_pipeline, data_pipelin_kwargs, max_len, params, monitor_actor)
        self.product = self.products[0]
        
        data_card = self.data_cards[0]
        data_card_index = self.create_data_index(data_card.product.exch, data_card.product.name, data_card.freq, aggregation=data_card.aggregation)
        self.data = self.datas[data_card_index]
        self.sma_indicator = SmaIndicator(
            data=self.data,
            min_period=self.params['period']
        )

    def next(self):
        """
        Override the on_bar method to handle bar updates and generate signals.
        """
        # if len(self.sma_indicator.sma) > 1:
        #     print('close[-1]={} sma[-1]={} close[-2]={} sma[-2]={}'.format(self.data[-1].close, self.sma_indicator.sma[-1], self.data[-2].close, self.sma_indicator.sma[-2]))

        # else:
        #     print('len sma={}'.format(len(self.sma_indicator.sma)))
        if self.data[-1].close > self.sma_indicator.sma[-1] and self.data[-2].close <= self.sma_indicator.sma[-2]:
            self.buy(
                gateway='mock_gateway',
                product=self.products[0],
                price=self.data[-1].close,
                size=1,
                order_type='MARKET',
                time_in_force='GTC',
            )
        elif self.data[-1].close < self.sma_indicator.sma[-1] and self.data[-2].close >= self.sma_indicator.sma[-2]:
            self.sell(
                gateway='mock_gateway',
                product=self.products[0],
                price=self.data[-1].close,
                size=1,
                order_type='MARKET',
                time_in_force='GTC',
            )
    
    def get_signals(self):
        return {
            'sma - close': self.sma_indicator.sma[-1] - self.data[-1].close,
        }
```

For more details, you can check the documentation here.

---

## Building My Own Data Pipeline

Research lives or dies on data quality. I built a small CLI-driven service called `trading-data` to collect and organize everything I might trade: crypto ticks from Binance and Bybit, minute bars for CME futures, daily OHLCV for stocks and ETFs.

The lake writes each data source to a folder tree under `~/.trading-data`, a single command like:

```bash
trading-data datalake update --name ib --start-date 2024-01-01
```

pulls fresh intraday data, updates the catalog, and logs provenance so I can reproduce any backtest months later.

Currently I've built the pipelines for Bybit, Binance, Firstrate data and Traders workstation. You can check the details on the README.md of my repo.

---

## Using Backtrader to Backtest Strategies

Even though I found Backtrader hard to debug in live trading, it's still a widely adopted backtesting engine. I chose not to reinvent the reel at this moment. I use it primarily for backtesting ideas, then transition winning strategies to Alchemist for live execution.

I integrate my data pipeline to load historical data to backtrader's cerebro. You may load historical data using the data pipeline like this:

```python
import pandas as pd

from trading_data.datalake_client import DatalakeClient
from trading_data.common.date_ranges import get_dates

def load_data(pdt: str, start_date: str, end_date: str, data_source: str) -> pd.DataFrame:
    dlc = DatalakeClient()
    dates = get_dates(start_date, end_date)
    dfs = []
    for date in dates:
        try:
            df = dlc.get_table(data_source, pdt, ver_name='min_bar', set_index=True, date=date)
            dfs.append(df)
        except:
            continue  # TODO can log the message for INFO
    df = pd.concat(dfs)
    return df
```

And then you can just build your strategy and a main script with backtrader like below:

```python
import pandas as pd
import backtrader as bt

# `quant-factory` is private repo for me to develop trading strategies
# All strategies inside are built with the open-sourced repos I mentioned in this article
from quant_factory.strategies.common import load_data
from quant_factory.strategies.intraday_bb_reversal_strategy.create_backtest_stratetgy import create_strategy
from quant_factory.analyzers import MetricsAnalyzer, TradeAnalyzer
from quant_factory.commissions import IBStockCommission

DEFAULT_STRAT_PARAMS = {
    'bollinger_period': 60,
    'bollinger_dev': 2.5,
    'bollinger_dev_exit': 2,
    'fast_sma_period': 20,
    'slow_sma_period': 60, 
    'atr_period': 15,
    'min_trade_equity': 2000,
}

BAR_TYPE = 'min_bar'

def run_backtest(asset, strat_params, start_date, end_date, initial_cash=100000, data_source='yfinance', plot=False):
    """
    Runs backtesting for the reversal strategy on a single asset.
    Returns the final portfolio value and various performance metrics.
    """
    # Load data
    df = load_data(asset, start_date, end_date, data_source)

    # Convert to Backtrader data feed
    data_feed = bt.feeds.PandasData(dataname=df)
    
    # Create Backtrader engine
    cerebro = bt.Cerebro()
    cerebro.adddata(data_feed)

    strat_params = {name: strat_params.get(name, DEFAULT_STRAT_PARAMS.get(name)) for name in DEFAULT_STRAT_PARAMS}
    
    # Add strategy
    StrategyClass = create_strategy(strat_params)
    cerebro.addstrategy(StrategyClass)
    
    # Set initial cash
    cerebro.broker.set_cash(initial_cash)
    
    # Set commission
    cerebro.broker.addcommissioninfo(IBStockCommission())
    
    # Add metrics analyzer
    cerebro.addanalyzer(MetricsAnalyzer, _name='metrics')
    cerebro.addanalyzer(TradeAnalyzer, _name='trades')
    
    # Run backtest
    results = cerebro.run()
    strat = results[0]
    
    if plot:
        cerebro.plot()

    # Get final portfolio value
    final_value = cerebro.broker.getvalue()
    
    # Compute metrics
    metrics = strat.analyzers.metrics.get_metrics()
    trades = strat.analyzers.trades.get_analysis()
    
    return final_value, metrics, trades
```

---

## My Philosophy of Strategy Development

When I am crafting strategies, I always focus on the speed from development to deployment. I believe that no process is more important than live trading. Backtesting is still important for giving you insights of how your strategy may perform. However, backtesting is only on history. Interaction data of your strategy with real-time data is more valuable than backtesting.

Therefore, my current development strategy is simple:

> Launch the rocket, let it crash, then learn.

This mirrors Elon Musk's approach at SpaceX: launch fast, fail fast, learn fast. I tried a more vigorous research approach to develop strategies, but it turned out that it costed too much time and resource before I got an running strategy. That kind of exhaustive research isn't feasible as a one-man operation. It would burn me out before I even shipped a single live strategy.
