import json
import logging
import os
import time
import urllib.parse
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

import boto3
import requests
from boto3.dynamodb.conditions import Key
from chalice import Chalice, Rate


app = Chalice(app_name="btc-momentum")

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"


def get_env_var(name: str) -> str:
    try:
        value = os.environ.get(name)
        if not value:
            raise ValueError(f"Missing required environment variable: {name}")
        return value
    except Exception as exc:
        logger.exception("Environment variable error: %s", exc)
        raise


def fetch_btc_price() -> Optional[Dict[str, Any]]:
    try:
        params = {
            "ids": "bitcoin",
            "vs_currencies": "usd",
            "include_market_cap": "true",
            "include_24hr_vol": "true",
            "include_24hr_change": "true",
            "include_last_updated_at": "true",
        }

        logger.info("Fetching BTC data from CoinGecko.")
        response = requests.get(COINGECKO_URL, params=params, timeout=15)
        logger.info("CoinGecko response status=%s", response.status_code)

        response.raise_for_status()
        data = response.json()

        if "bitcoin" not in data:
            logger.error("Unexpected CoinGecko response: %s", data)
            return None

        return data["bitcoin"]

    except requests.exceptions.Timeout:
        logger.exception("CoinGecko request timed out.")
        return None
    except requests.exceptions.HTTPError as exc:
        logger.exception("CoinGecko HTTP error: %s", exc)
        return None
    except requests.exceptions.RequestException as exc:
        logger.exception("CoinGecko request failed: %s", exc)
        return None
    except Exception as exc:
        logger.exception("Unexpected error fetching BTC price: %s", exc)
        return None


def build_btc_item(price_data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        sample_ts = int(time.time())
        sample_datetime_utc = datetime.fromtimestamp(
            sample_ts, tz=timezone.utc
        ).isoformat()

        item = {
            "asset": get_env_var("ASSET"),
            "sample_ts": sample_ts,
            "sample_datetime_utc": sample_datetime_utc,
            "price_usd": Decimal(str(price_data["usd"])),
            "market_cap_usd": Decimal(str(price_data["usd_market_cap"])),
            "volume_24h_usd": Decimal(str(price_data["usd_24h_vol"])),
            "change_24h_pct": Decimal(str(price_data["usd_24h_change"])),
            "source_last_updated_at": Decimal(str(price_data["last_updated_at"])),
            "source": "coingecko",
        }

        logger.info("Built BTC item: %s", item)
        return item

    except KeyError as exc:
        logger.exception("Missing expected field from CoinGecko response: %s", exc)
        raise
    except Exception as exc:
        logger.exception("Failed to build BTC item: %s", exc)
        raise


def get_table():
    try:
        return dynamodb.Table(get_env_var("DYNAMODB_TABLE"))
    except Exception as exc:
        logger.exception("Failed to connect to DynamoDB table: %s", exc)
        raise


def write_item_to_dynamodb(item: Dict[str, Any]) -> bool:
    try:
        table = get_table()
        table.put_item(Item=item)

        logger.info(
            "Wrote item to DynamoDB. asset=%s sample_ts=%s price=%s",
            item["asset"],
            item["sample_ts"],
            item["price_usd"],
        )

        return True

    except Exception as exc:
        logger.exception("Failed writing item to DynamoDB: %s", exc)
        return False


def get_recent_items(limit: int = 96) -> List[Dict[str, Any]]:
    try:
        table = get_table()

        response = table.query(
            KeyConditionExpression=Key("asset").eq(get_env_var("ASSET")),
            ScanIndexForward=False,
            Limit=limit,
        )

        items = response.get("Items", [])
        items.sort(key=lambda x: int(x["sample_ts"]))

        logger.info("Loaded %s recent DynamoDB items.", len(items))
        return items

    except Exception as exc:
        logger.exception("Failed querying recent BTC items: %s", exc)
        return []


def get_latest_item() -> Optional[Dict[str, Any]]:
    try:
        items = get_recent_items(limit=1)

        if not items:
            logger.warning("No BTC items found in DynamoDB.")
            return None

        return items[-1]

    except Exception as exc:
        logger.exception("Failed getting latest BTC item: %s", exc)
        return None


@app.schedule(Rate(15, unit=Rate.MINUTES))
def ingest_btc_price(event):
    logger.info("Starting scheduled BTC ingestion job.")

    try:
        price_data = fetch_btc_price()

        if price_data is None:
            logger.error("BTC fetch failed.")
            return {
                "status": "failed_fetch",
                "message": "CoinGecko fetch failed. Check CloudWatch logs.",
            }

        item = build_btc_item(price_data)
        success = write_item_to_dynamodb(item)

        if not success:
            logger.error("DynamoDB write failed.")
            return {
                "status": "failed_write",
                "message": "DynamoDB write failed. Check CloudWatch logs.",
            }

        logger.info("BTC ingestion finished successfully.")

        return {
            "status": "success",
            "asset": item["asset"],
            "sample_ts": item["sample_ts"],
            "price_usd": float(item["price_usd"]),
            "change_24h_pct": float(item["change_24h_pct"]),
        }

    except Exception as exc:
        logger.exception("Fatal error in BTC ingestion: %s", exc)
        return {
            "status": "fatal_error",
            "message": str(exc),
        }


@app.route("/")
def index():
    return {
        "about": "BTC Momentum tracks Bitcoin price, market cap, trading volume, and 24-hour movement every 15 minutes.",
        "resources": ["current", "trend", "volatility", "plot"],
    }


@app.route("/current")
def current():
    try:
        item = get_latest_item()

        if not item:
            return {"response": "No BTC data has been collected yet."}

        price = float(item["price_usd"])
        change = float(item["change_24h_pct"])
        ts = item["sample_datetime_utc"]

        return {
            "response": f"BTC is currently ${price:,.2f}. 24h change: {change:.2f}%. Last sampled at {ts}."
        }

    except Exception as exc:
        logger.exception("Error in /current: %s", exc)
        return {"response": "Error loading current BTC price."}


@app.route("/trend")
def trend():
    try:
        items = get_recent_items(limit=96)

        if len(items) < 2:
            return {"response": "Not enough data yet to calculate trend."}

        first = float(items[0]["price_usd"])
        latest = float(items[-1]["price_usd"])
        pct_change = ((latest - first) / first) * 100

        return {
            "response": f"BTC changed {pct_change:.2f}% across the collected window. Start: ${first:,.2f}, latest: ${latest:,.2f}."
        }

    except Exception as exc:
        logger.exception("Error in /trend: %s", exc)
        return {"response": "Error calculating BTC trend."}


@app.route("/volatility")
def volatility():
    try:
        items = get_recent_items(limit=96)

        if len(items) < 2:
            return {"response": "Not enough data yet to calculate volatility."}

        prices = [float(item["price_usd"]) for item in items]
        min_price = min(prices)
        max_price = max(prices)
        latest = prices[-1]

        range_pct = ((max_price - min_price) / latest) * 100

        return {
            "response": f"BTC volatility window: price range ${min_price:,.2f} to ${max_price:,.2f}, equal to {range_pct:.2f}% of the latest price."
        }

    except Exception as exc:
        logger.exception("Error in /volatility: %s", exc)
        return {"response": "Error calculating BTC volatility."}


@app.route("/plot")
def plot():
    try:
        bucket = get_env_var("PLOT_BUCKET")
        key = get_env_var("PLOT_KEY")
        url = f"https://{bucket}.s3.amazonaws.com/{key}"

        return {"response": url}

    except Exception as exc:
        logger.exception("Error in /plot: %s", exc)
        return {"response": "Error returning BTC plot URL."}