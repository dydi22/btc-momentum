# BTC Momentum Tracker

BTC Momentum Tracker is a serverless data project that tracks Bitcoin market movement over time. It collects BTC price, market cap, 24-hour trading volume, and 24-hour percent change every 15 minutes.

## Data Source

This project uses the public CoinGecko API to collect Bitcoin market data. BTC is a meaningful changing data source because its price updates continuously, and a time series can reveal momentum, volatility, and short-term market movement.

## Ingestion Pipeline

The ingestion pipeline uses:

- EventBridge scheduled rule
- AWS Lambda
- CoinGecko API
- DynamoDB
- CloudWatch Logs

The Lambda function runs every 15 minutes:

```text
rate(15 minutes)

```

# BTC Momentum Tracker

## Storage Schema

### DynamoDB Table

| Attribute Name | Type | Key Type | Description |
|---------------|------|----------|-------------|
| asset | String | Partition Key | Asset identifier (BTC) |
| sample_ts | Number | Sort Key | Unix timestamp of sample |

### Data Fields

| Field | Type | Description |
|------|------|------------|
| asset | String | Asset being tracked |
| sample_ts | Number | Unix timestamp |
| sample_datetime_utc | String | UTC timestamp |
| price_usd | Number | BTC price in USD |
| market_cap_usd | Number | BTC market cap |
| volume_24h_usd | Number | 24-hour trading volume |
| change_24h_pct | Number | 24-hour percent change |
| source_last_updated_at | Number | Source timestamp |
| source | String | Data source (coingecko) |

---

## API Resources

### Base API

https://hhgx23sgx6.execute-api.us-east-1.amazonaws.com/api

---

### Available Resources

| Resource | Endpoint | Description |
|----------|----------|------------|
| current | /current | Latest BTC price and 24h change |
| trend | /trend | Percent change over recent samples |
| volatility | /volatility | Price range and volatility |
| plot | /plot | Link to BTC price plot |

---

## Example Outputs

### current

BTC is currently $79,802.00. 24h change: 2.16%. Last sampled at a recent timestamp.

### trend

BTC moved a small percentage over the last few hours.

### volatility

BTC price ranged between recent highs and lows with a small volatility percentage.

### plot

Returns a public S3 URL to a PNG image showing BTC price over time.

---

## Logging and Exception Handling

### Logging

The application logs:

- Lambda execution start and completion  
- API requests to CoinGecko  
- HTTP response status codes  
- Data parsing steps  
- DynamoDB writes and reads  
- API endpoint execution  
- Errors and failures  

All logs are stored in AWS CloudWatch Logs.

---

### Exception Handling

The system uses try/except blocks for:

- API request failures  
- JSON parsing errors  
- DynamoDB read/write failures  
- Missing environment variables  
- API endpoint errors  

If something fails, the API returns a safe response instead of crashing.

---

## Notes

- Data is collected every 15 minutes  
- Data is stored in DynamoDB  
- Plot is generated and stored in S3  
- API is deployed using Chalice  
