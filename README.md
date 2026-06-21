# ReviewInsight AI — Amazon Product Reviews Analytics

Automated sentiment analysis and topic extraction from 500K+ customer reviews using LLM.

![Dashboard Screenshot](docs/dashboard.png)
![Dashboard Screenshot](docs/topics.png)
![Dashboard Screenshot](docs/sample.png)

## 🎯 Business Value

This tool helps businesses:
- **Save 20+ hours/week** of manual review analysis
- **Identify key customer pain points** automatically
- **Track sentiment trends** over time
- **Make data-driven decisions** based on real customer feedback

## 🏗 Architecture

```
CSV (568K reviews) → pandas → OpenRouter API (Llama-3) → SQLite → Streamlit Dashboard
```

**Key decisions:**
- **OpenRouter API** — cost-effective, multiple models, no credit card required
- **SQLite** — zero-config for demo, easily migratable to PostgreSQL
- **Streamlit** — rapid dashboard development without frontend expertise
- **Llama-3 8B** — fast, accurate, supports structured JSON output

## 🚀 Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/review-insight-ai.git
cd review-insight-ai
```

### 2. Install dependencies
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Set up OpenRouter API key
Get your free API key at https://openrouter.ai

Create `.env` file:
```
OPENROUTER_API_KEY=your_key_here
```

### 4. Run ingestion pipeline
```bash
python ingest.py
```

This will analyze the first 50 reviews from `data/reviews.csv` and save results to `data/reviews.db`.

### 5. Launch dashboard
```bash
streamlit run dashboard.py
```

Open http://localhost:8501 in your browser.

## 📊 Dataset

This project uses the [Amazon Fine Food Reviews](https://www.kaggle.com/datasets/arhamrumi/amazon-product-reviews) dataset from Kaggle:
- 568,454 reviews
- October 1999 - October 2012
- Real customer feedback with ratings

**To run this project:**
1. Download the dataset from Kaggle (link above)
2. Place `reviews.csv` in the `data/` folder
3. Run `python ingest.py`

Note: The dataset is not included in this repository due to its size (286 MB).

## 🛠 Tech Stack

- **Python 3.11**
- **LangChain** — LLM orchestration
- **OpenRouter API** — LLM provider (Llama-3 8B)
- **SQLite** — lightweight database
- **Streamlit** — dashboard framework
- **Plotly** — interactive visualizations
- **pandas** — data processing

## 📈 Future Improvements

- [ ] Migrate to PostgreSQL for production
- [ ] Add batch processing for all 568K reviews
- [ ] Implement real-time monitoring
- [ ] Add export to CSV/PDF
- [ ] Docker containerization

## 📄 License

MIT License