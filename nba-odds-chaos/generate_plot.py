import io
from datetime import datetime, timezone

import boto3
import matplotlib.pyplot as plt
from boto3.dynamodb.conditions import Key


DYNAMODB_TABLE = "btc-momentum"
ASSET = "BTC"

PLOT_BUCKET = "btc-momentum-plot-dylan"
PLOT_KEY = "dp3/btc-momentum/latest.png"


dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
s3 = boto3.client("s3", region_name="us-east-1")


def load_btc_data(limit=96):
    table = dynamodb.Table(DYNAMODB_TABLE)

    response = table.query(
        KeyConditionExpression=Key("asset").eq(ASSET),
        ScanIndexForward=False,
        Limit=limit,
    )

    items = response.get("Items", [])
    items.sort(key=lambda x: int(x["sample_ts"]))

    return items


def generate_plot(items):
    times = [
        datetime.fromtimestamp(int(item["sample_ts"]), tz=timezone.utc)
        for item in items
    ]

    prices = [float(item["price_usd"]) for item in items]

    plt.figure(figsize=(11, 5))
    plt.plot(times, prices, marker="o", linewidth=2)

    plt.title("BTC Momentum Tracker — Price Over Time")
    plt.xlabel("Time UTC")
    plt.ylabel("BTC Price USD")
    plt.xticks(rotation=35)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()

    buffer = io.BytesIO()
    plt.savefig(buffer, format="png", dpi=150)
    plt.close()
    buffer.seek(0)

    return buffer


def upload_plot(buffer):
    s3.put_object(
        Bucket=PLOT_BUCKET,
        Key=PLOT_KEY,
        Body=buffer.getvalue(),
        ContentType="image/png",
    )

    url = f"https://{PLOT_BUCKET}.s3.amazonaws.com/{PLOT_KEY}"
    return url


def main():
    items = load_btc_data()

    if len(items) < 2:
        print("Not enough data yet. Run the ingestion Lambda a few more times.")
        return

    buffer = generate_plot(items)
    url = upload_plot(buffer)

    print("Uploaded plot:")
    print(url)


if __name__ == "__main__":
    main()
