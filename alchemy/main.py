# This file will be moved to alchemy/main.py as part of the package structure.
import os
import sys
import time
from datetime import datetime, timedelta
import ray
from alchemist.account import Account
from alchemist.data_card import DataCard
from alchemist.products.stock_product import StockProduct
from alchemist.gateways.ib_gateway import IbGateway

accounts = [Account(**account)]
products = [
    StockProduct(
        name=products[i]["name"],
        base_currency=products[i]["base_currency"],
        exch=products[i]["exch"],
    )
    for i in range(len(products))
]
data_cards = [
    DataCard(
        product=products[i],
        freq=data_cards[i]["freq"],
        aggregation=data_cards[i]["aggregation"],
    )
    for i in range(len(data_cards))
]

monitor_actor = TelegramMonitor.remote(
    bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
    chat_id=os.getenv("TELEGRAM_CHAT_ID"),
    flush_interval=60.0,
    is_test=False,
)
strategy_actor = BBReversalStrategy.remote(
    name=strategy["name"],
    zmq_send_port=strategy["zmq_send_port"],
    zmq_recv_ports=strategy["zmq_recv_ports"],
    products=products,
    data_cards=data_cards,
    data_pipeline='IBDataPipeline',  # REMINDER: this must be a class name. it will be imported inside the actor process
    data_pipeline_kwargs={
        'account': accounts[0],
    },
    monitor_actor=monitor_actor
)
gateway_actor = IbGateway.remote(
    subscriptions=gateway["subscriptions"],
    zmq_send_port=gateway["zmq_send_port"],
    zmq_recv_ports=gateway["zmq_recv_ports"],
    accounts=accounts,
    products=products,
)


# start backfilling
backfill_start_date = (datetime.now() - timedelta(days=2)).strftime(
    "%Y-%m-%d"
)  # TEMP: fill 2 days of min bar data

ray.get(
    strategy_actor.start_backfilling.remote(
        backfilling_start_date=backfill_start_date,
    )
)

gateway_actor.start.remote()
strategy_actor.start.remote()

# Passive run loop (could evolve into a monitoring system)
market_close_time = datetime.now().replace(
    hour=16, minute=0, second=0, microsecond=0
)
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
