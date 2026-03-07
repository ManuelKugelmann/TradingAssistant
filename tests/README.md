# Tests

## Running Tests

```bash
# Unit tests (mocked, no API keys needed)
pytest tests/test_store.py tests/test_servers.py -v

# Integration tests (hits real APIs, keys optional)
pytest tests/test_integration.py -v

# All tests
pytest -v
```

## Test Structure

| File | Tests | Requires |
|------|-------|----------|
| `test_store.py` | Signals store: profiles, indexes, lint, snapshots (mocked MongoDB) | Nothing |
| `test_servers.py` | All 12 domain servers: mocked HTTP via respx | Nothing |
| `test_integration.py` | Live API calls, skipped if keys missing | API keys (optional) |

## GitHub Secrets for CI Integration Tests

Add these secrets in **Settings > Secrets and variables > Actions > Repository secrets**:

| Secret Name | Service | Required for | Signup URL |
|-------------|---------|-------------|------------|
| `FRED_API_KEY` | FRED (Federal Reserve) | `TestFredIntegration` | https://fred.stlouisfed.org/docs/api/api_key.html |
| `ACLED_API_KEY` | ACLED (armed conflict) | `TestAcledIntegration` | https://acleddata.com/register/ |
| `ACLED_EMAIL` | ACLED (paired with key) | `TestAcledIntegration` | same as above |
| `EIA_API_KEY` | EIA (US energy data) | `TestEiaIntegration` | https://www.eia.gov/opendata/register.php |
| `COMTRADE_API_KEY` | UN Comtrade (trade) | `TestComtradeIntegration` | https://comtradeplus.un.org/ |
| `GOOGLE_API_KEY` | Google Civic Info | `TestGoogleCivicIntegration` | https://console.cloud.google.com/apis/credentials |
| `AISSTREAM_API_KEY` | AIS vessel tracking | `TestAisStreamIntegration` | https://aisstream.io/ |
| `CF_API_TOKEN` | Cloudflare Radar | `TestCloudflareIntegration` | https://dash.cloudflare.com/profile/api-tokens |
| `USDA_NASS_API_KEY` | USDA crop data | `TestUsdaIntegration` | https://quickstats.nass.usda.gov/api/ |

**Note:** All integration tests with API keys are skipped when the key is not set.
The `TestFreeApiIntegration` class tests 8 free/no-auth APIs and runs without any secrets.

## Dependencies

```
pytest
pytest-asyncio
respx
httpx
fastmcp>=2.0
pymongo
python-dotenv
```
