import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import json
from datetime import datetime

# Заголовок
st.set_page_config(page_title="ReviewInsight AI", layout="wide")
st.title("ReviewInsight AI — Amazon Product Reviews Analytics")
st.subheader("Automated sentiment analysis and topic extraction from 500K+ customer reviews")

# Подключение к БД
@st.cache_data
def load_data():
    conn = sqlite3.connect('./data/reviews.db')
    df = pd.read_sql_query("SELECT * FROM reviews_analysis ORDER BY analyzed_at DESC", conn)
    conn.close()
    
    # Парсим topics из JSON с обработкой ошибок
    def parse_topics(x):
        if not x or x == 'error' or x == '[]':
            return []
        try:
            parsed = json.loads(x)
            if isinstance(parsed, list):
                # Фильтруем не-строковые значения
                return [t for t in parsed if isinstance(t, str) and len(t) > 1]
            return []
        except:
            return []
    
    df['topics_list'] = df['topics'].apply(parse_topics)
    
    # Конвертируем дату
    df['analyzed_at'] = pd.to_datetime(df['analyzed_at'])
    df['date'] = df['analyzed_at'].dt.date
    
    return df

# Загрузка данных
try:
    df = load_data()
except Exception as e:
    st.error(f"Error loading data: {e}")
    st.stop()

# Проверка на пустую БД
if df.empty:
    st.warning("No data available. Run ingest.py first.")
    st.stop()

# Sidebar фильтр
st.sidebar.header("Filter by Sentiment")
sentiment_filter = st.sidebar.selectbox(
    "Select sentiment:",
    ["All", "Positive", "Negative", "Neutral"]
)

if sentiment_filter != "All":
    df_filtered = df[df['sentiment'] == sentiment_filter.lower()]
else:
    df_filtered = df

# Метрика вверху
col1, col2, col3 = st.columns(3)
col1.metric("Total Reviews Analyzed", len(df_filtered))
col2.metric("Positive", len(df_filtered[df_filtered['sentiment'] == 'positive']))
col3.metric("Negative", len(df_filtered[df_filtered['sentiment'] == 'negative']))

# Круговая диаграмма: Sentiment Distribution (голубая гамма)
st.subheader("Sentiment Distribution")
sentiment_counts = df_filtered['sentiment'].value_counts().reset_index()
sentiment_counts.columns = ['Sentiment', 'Count']
fig_pie = px.pie(sentiment_counts, values='Count', names='Sentiment', 
                 color='Sentiment',
                 color_discrete_map={
                     'positive': '#87CEEB',
                     'negative': '#4682B4',
                     'neutral': '#B0E0E6'
                 })
st.plotly_chart(fig_pie, use_container_width=True)

# Бар-чарт: Top 5 Customer Topics (голубая гамма)
st.subheader("Top 5 Customer Topics")
all_topics = [topic for topics_list in df_filtered['topics_list'] for topic in topics_list]
if all_topics:
    topics_df = pd.DataFrame(all_topics, columns=['Topic'])
    top_topics = topics_df['Topic'].value_counts().head(5).reset_index()
    top_topics.columns = ['Topic', 'Count']
    fig_bar = px.bar(top_topics, x='Topic', y='Count', 
                     labels={'Topic': 'Topic', 'Count': 'Count'},
                     color='Count',
                     color_continuous_scale='Blues')
    st.plotly_chart(fig_bar, use_container_width=True)
else:
    st.info("No topics available")

# Линейный график: Sentiment Trend Over Time (голубая гамма)
st.subheader("Sentiment Trend Over Time")
trend_df = df_filtered.groupby(['date', 'sentiment']).size().reset_index(name='Count')
fig_line = px.line(trend_df, x='date', y='Count', color='sentiment',
                   labels={'date': 'Date', 'Count': 'Count', 'sentiment': 'Sentiment'},
                   color_discrete_map={
                       'positive': '#87CEEB',
                       'negative': '#4682B4',
                       'neutral': '#B0E0E6'
                   })
st.plotly_chart(fig_line, use_container_width=True)

# Таблица с примерами
st.subheader("Sample Reviews")
st.dataframe(
    df_filtered[['original_text', 'sentiment', 'summary']].head(20),
    column_config={
        "original_text": st.column_config.TextColumn("Original Review", width="large"),
        "sentiment": st.column_config.TextColumn("Sentiment"),
        "summary": st.column_config.TextColumn("Summary", width="large")
    },
    hide_index=True
)