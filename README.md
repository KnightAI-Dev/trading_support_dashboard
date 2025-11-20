# Trading Support Architecture

A production-ready microservices architecture for real-time trading signal generation, market analysis, and actionable trading insights from exchange data.

## 🏗️ Architecture Overview

This system processes market data from exchanges (Binance) and generates trading signals with:
- **Swing High/Low Detection**
- **Support & Resistance Levels**
- **Fibonacci Entry/Exit Points**
- **Confluence Scoring** (Order Blocks, S/R, RSI, Fibonacci)
- **Risk-Reward Calculations**
- **Pullback Detection**

### System Architecture

```
┌─────────────────┐
│  Binance API    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Ingestion       │──► PostgreSQL/TimescaleDB
│ Service         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Processing      │──► Redis (Pub/Sub)
│ Service         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Worker Service  │──► Celery Tasks
│ (Celery)        │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│ Swing  │ │   SR   │ │  Fib   │ │Conflu- │ │  Risk  │
│ Engine │ │ Engine │ │ Engine │ │ ence   │ │ Engine │
└───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘ └───┬────┘
    │          │          │          │          │
    └──────────┴──────────┴──────────┴──────────┘
                    │
                    ▼
            ┌───────────────┐
            │ Storage       │
            │ Service       │
            └───────┬───────┘
                    │
                    ▼
            ┌───────────────┐
            │  API Service  │──► FastAPI REST API
            │  (FastAPI)     │
            └───────────────┘
```

## 📁 Project Structure

```
trading_support_dashboard/
├── database/
│   └── init.sql                 # TimescaleDB schema
├── shared/                      # Shared utilities
│   ├── __init__.py
│   ├── database.py              # Database connection
│   ├── models.py                # SQLAlchemy models
│   ├── config.py                # Configuration
│   ├── logger.py                # Logging setup
│   └── redis_client.py          # Redis client
├── services/
│   ├── ingestion-service/       # Binance data ingestion
│   ├── processing-service/      # OHLCV processing
│   ├── swing-engine/            # Swing point detection
│   ├── sr-engine/               # Support/Resistance
│   ├── fib-entry-engine/        # Fibonacci levels
│   ├── confluence-engine/       # Confluence scoring
│   ├── risk-engine/             # Risk-reward calculations
│   ├── api-service/             # FastAPI REST API
│   └── worker-service/           # Celery task queue
├── docker-compose.yml           # Docker orchestration
├── env.example                  # Environment variables template
└── README.md
```

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)

### 1. Clone and Setup

```bash
git clone <repository>
cd trading_support_dashboard
cp env.example .env
# Edit .env with your configuration
```

### 2. Start Services

```bash
docker-compose up -d
```

This will start:
- PostgreSQL/TimescaleDB (port 5432)
- Redis (port 6379)
- All microservices

### 3. Verify Services

```bash
# Check API health
curl http://localhost:8000/health

# View API documentation
open http://localhost:8000/docs
```

## 📊 Database Schema

### Key Tables

- **ohlcv_candles**: Time-series OHLCV data (hypertable)
- **market_data**: Open interest, CVD, net longs/shorts
- **swing_points**: Detected swing highs and lows
- **support_resistance**: S/R levels with strength
- **fibonacci_levels**: Fibonacci retracement levels
- **trading_signals**: Main output table with all signals
- **confluence_factors**: Individual confluence scores
- **fib_config**: Fibonacci configuration (long/short setups)

### TimescaleDB Features

- Automatic time-series partitioning
- Optimized queries for time-range data
- Continuous aggregates support

## 🔧 Configuration

### Fibonacci Configuration

**Long Setup:**
- Entry Level 1: 0.70
- Entry Level 2: 0.72
- Stop Loss: 0.90
- Approaching Level: 0.618

**Short Setup:**
- Entry Level 1: 0.618
- Entry Level 2: 0.69
- Stop Loss: 0.789
- Approaching Level: 0.5

**Pullback Start:** 0.382

### Environment Variables

See `env.example` for all configuration options:

- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `BINANCE_API_URL`: Binance API endpoint
- `DEFAULT_TIMEFRAME`: Default timeframe (1h, 4h, 1d, etc.)
- `DEFAULT_SYMBOLS`: Comma-separated symbols (BTCUSDT,ETHUSDT)

## 📡 API Endpoints

### Trading Signals

```bash
# Get all signals
GET /signals

# Get latest signal for symbol
GET /signals/{symbol}/latest

# Get signals summary
GET /signals/summary

# Filter signals
GET /signals?symbol=BTCUSDT&direction=long&limit=10
```

### Market Data

```bash
# Get OHLCV candles
GET /candles/{symbol}?timeframe=1h&limit=100

# Get support/resistance levels
GET /sr-levels/{symbol}?timeframe=1h

# Get swing points
GET /swings/{symbol}?timeframe=1h
```

### Example Response

```json
{
  "symbol": "BTCUSDT",
  "market_score": 95,
  "direction": "long",
  "price": 102244,
  "entry1": 101718,
  "entry2": 101750,
  "sl": 101062,
  "tp1": 102374,
  "tp2": 102761,
  "tp3": 103240,
  "swing_high": 104010,
  "swing_low": 100734,
  "support_level": 101582,
  "resistance_level": null,
  "confluence": "OB,SR,RSI",
  "risk_reward_ratio": 2.5,
  "confidence_score": 87.5
}
```

## 🔄 Data Flow

1. **Ingestion Service** fetches OHLCV data from Binance every minute
2. **Processing Service** detects new candles and triggers analysis
3. **Worker Service** processes analysis pipeline:
   - Swing detection
   - S/R detection
   - Fibonacci calculation
   - Confluence scoring
   - Risk-reward calculation
4. **Storage module** (in `shared/`) saves final trading signal
5. **API Service** exposes signals via REST API

## 🧪 Development

### Running Services Locally

```bash
# Start dependencies
docker-compose up -d postgres redis

# Run service locally
cd services/ingestion-service
python main.py
```

### Testing

```bash
# Test API
curl http://localhost:8000/signals/BTCUSDT/latest

# Test database connection
python -c "from shared.database import init_db; init_db()"
```

## 📈 Output Format

The system generates trading signals in this format:

| Symbol | Market Score | Direction | Price | Entry1 | SL | TP1 | TP2 | TP3 | SwingHigh | SwingLow | S/R | Confluence |
|--------|-------------|-----------|-------|--------|----|----|----|----|-----------|----------|-----|------------|
| BTCUSDT | 95 | long | 102244 | 101718 | 101062 | 102374 | 102761 | 103240 | 104010 | 100734 | 101582 | OB, SR |
| SOLUSDT | 93 | short | 156.01 | 157.17 | 159.92 | 154.82 | 153.37 | 151.02 | 160.97 | 151.02 | 156.77 | OB, SR, RSI |

## 🛠️ Services Details

### Ingestion Service
- Fetches OHLCV klines from Binance
- Updates market data (price, volume)
- Publishes candle updates to Redis

### Processing Service
- Monitors for new candles
- Triggers analysis pipeline
- Prevents duplicate processing

### Swing Engine
- Detects swing highs/lows using lookback periods
- Configurable strength (default: 5 periods)

### S/R Engine
- Clusters price levels
- Tracks touch count for strength
- Maintains active/inactive levels

### Fibonacci Engine
- Calculates retracement levels
- Determines entry/exit points based on config
- Detects pullback zones

### Confluence Engine
- Scores signals based on multiple factors:
  - Order Blocks (OB)
  - Support/Resistance (SR)
  - RSI overbought/oversold
  - Fibonacci levels
  - Swing points
- Generates 0-100 market score

### Risk Engine
- Calculates risk-reward ratios
- Validates setup criteria
- Computes confidence scores

### Storage Module (shared/storage.py)
- Database abstraction layer
- Signal persistence
- Data retrieval operations
- Used by API service and worker service

### API Service
- FastAPI REST API
- OpenAPI documentation
- CORS enabled

### Worker Service
- Celery task queue
- Async processing
- Full analysis pipeline orchestration

## 🔍 Monitoring

### Logs

```bash
# View all logs
docker-compose logs -f

# View specific service
docker-compose logs -f api-service
```

### Database Queries

```sql
-- Latest signals
SELECT * FROM latest_signals;

-- Signal count by symbol
SELECT symbol, COUNT(*) FROM trading_signals GROUP BY symbol;

-- Average market score
SELECT AVG(market_score) FROM trading_signals;
```

## 🚨 Troubleshooting

### Database Connection Issues

```bash
# Check PostgreSQL
docker-compose ps postgres
docker-compose logs postgres

# Test connection
psql -h localhost -U trading_user -d trading_db
```

### Redis Connection Issues

```bash
# Check Redis
docker-compose ps redis
redis-cli -h localhost ping
```

### Service Not Starting

```bash
# Check service logs
docker-compose logs <service-name>

# Restart service
docker-compose restart <service-name>
```

## 📝 Notes

- **No Backtesting**: This system is for real-time signal generation only
- **Production Ready**: All services include logging, error handling, and retry logic
- **Scalable**: Microservices architecture allows horizontal scaling
- **Modular**: Each engine can be run independently or as part of pipeline

## 🔐 Security

- Use environment variables for sensitive data
- Never commit `.env` files
- Use API keys for production Binance access
- Implement rate limiting for API endpoints

## 📄 License

See LICENSE file for details.

## 🤝 Contributing

1. Follow the microservices architecture
2. Add logging and error handling
3. Include type hints
4. Write production-ready code
5. Test before submitting

---

**Built for algorithmic trading support and real-time market analysis.**
