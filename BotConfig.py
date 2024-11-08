import os
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class BotConfig:
    def __init__(
        self,
        user_id: str,
        bot_id: str,
        repository_url: str,
        broker: str
    ):
        self.user_id = user_id
        self.bot_id = bot_id
        self.broker = broker
        self.repository_url = repository_url

        self.build_parameters = {}
        if self.broker == "interactive_brokers":
            self.build_parameters["IB_USERNAME"] = "True"

        self.image: Optional[str] = None
        if self.broker == "interactive_brokers":
            self.resources = {
                "limits": {
                    "cpu": "1",
                    "memory": "1Gi"
                }
            }
        else:
            self.resources = {
                "limits": {
                    "cpu": os.getenv("CPU_LIMIT", "0.5"),
                    "memory": os.getenv("MEMORY_LIMIT", "512Mi"),
                }
            }

        self.broker_config = self._load_broker_configuration()

    def _load_broker_configuration(self) -> Dict:
        if self.broker == "alpaca":
            return self._load_alpaca_configuration()
        elif self.broker == "tradier":
            return self._load_tradier_configuration()
        elif self.broker == "kraken":
            return self._load_kraken_configuration()
        elif self.broker == "coinbase":
            return self._load_coinbase_configuration()
        elif self.broker == "interactive_brokers":
            return self._load_ib_rest_configuration()
        else:
            logger.error(f"Unsupported broker: {self.broker}")
            raise ValueError("Unsupported broker specified.")

    def _load_alpaca_configuration(self) -> Dict:
        return {
            "API_KEY": os.getenv("ALPACA_API_KEY"),
            "API_SECRET": os.getenv("ALPACA_API_SECRET"),
            "PAPER": os.getenv("ALPACA_IS_PAPER", "true").lower() == "true"
        }

    def _load_tradier_configuration(self) -> Dict:
        return {
            "ACCESS_TOKEN": os.getenv("TRADIER_ACCESS_TOKEN"),
            "ACCOUNT_NUMBER": os.getenv("TRADIER_ACCOUNT_NUMBER"),
            "PAPER": os.getenv("TRADIER_IS_PAPER", "true").lower() == "true"
        }

    def _load_kraken_configuration(self) -> Dict:
        return {
            "exchange_id": "kraken",
            "apiKey": os.getenv("KRAKEN_API_KEY"),
            "secret": os.getenv("KRAKEN_API_SECRET"),
            "margin": True,
            "sandbox": False,
        }

    def _load_coinbase_configuration(self) -> Dict:
        return {
            "exchange_id": "coinbase",
            "apiKey": os.getenv("COINBASE_API_KEY"),
            "secret": os.getenv("COINBASE_API_SECRET"),
            "margin": False,
            "sandbox": False,
        }

    def _load_ib_rest_configuration(self) -> Dict:
        return {
            "IB_USERNAME": os.getenv("IB_USERNAME"),
            "IB_PASSWORD": os.getenv("IB_PASSWORD"),
            "ACCOUNT_ID": os.getenv("ACCOUNT_ID"),
            "API_URL": None,
            "RUNNING_ON_SERVER": True
        }