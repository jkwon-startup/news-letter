import streamlit as st
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import schedule
import time
from datetime import datetime
import pandas as pd
import plotly.express as px
import hashlib
import os
from dotenv import load_dotenv

# Streamlit 페이지 설정
st.set_page_config(page_title="AI and Startup News Aggregator", layout="wide")

# 환경 변수 로드
load_dotenv()

# Google Sheets API 설정
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SERVICE_ACCOUNT_FILE = os.getenv('SERVICE_ACCOUNT_FILE')
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')

# 이메일 설정
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv('SENDER_EMAIL')
SENDER_PASSWORD = os.getenv('SENDER_PASSWORD')

# 관리자 인증 정보
ADMIN_USERNAME = os.getenv('ADMIN_USERNAME')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')

def get_google_sheets_service():
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return build('sheets', 'v4', credentials=creds)

def save_subscriber(name, email, keywords):
    service = get_google_sheets_service()
    sheet = service.spreadsheets()
    values = [[name, email, ','.join(keywords), str(datetime.now())]]
    body = {'values': values}
    sheet.values().append(spreadsheetId=SPREADSHEET_ID, range='Subscribers!A:D', 
                          valueInputOption='USER_ENTERED', body=body).execute()

def get_subscribers():
    service = get_google_sheets_service()
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range='Subscribers!A:D').execute()
    return result.get('values', [])[1:]  # Exclude header row

def crawl_news(keyword, num_articles=5):
    url = f"https://search.naver.com/search.naver?where=news&query={keyword}"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    news_items = soup.select('.news_area')[:num_articles]
    
    news_list = []
    for item in news_items:
        title = item.select_one('.news_tit')['title']
        link = item.select_one('.news_tit')['href']
        news_list.append({'title': title, 'link': link})
    
    return news_list

def send_newsletter(subscriber, ai_news, startup_news, custom_message):
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = subscriber['email']
    msg['Subject'] = "Your Daily AI and Startup News"

    body = f"""
    Hello {subscriber['name']},

    {custom_message}

    Here are your daily news updates:

    AI News:
    """
    for news in ai_news:
        body += f"- {news['title']}\n  {news['link']}\n\n"
    
    body += "\nStartup News:\n"
    for news in startup_news:
        body += f"- {news['title']}\n  {news['link']}\n\n"

    msg.attach(MIMEText(body, 'plain'))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)

def send_daily_newsletters(custom_message):
    ai_news = crawl_news("AI", 5)
    startup_news = crawl_news("startup", 5)
    subscribers = get_subscribers()
    
    for subscriber in subscribers:
        keywords = subscriber[2].split(',')
        if 'AI' in keywords or 'startup' in keywords:
            send_newsletter(
                {'name': subscriber[0], 'email': subscriber[1]},
                ai_news if 'AI' in keywords else [],
                startup_news if 'startup' in keywords else [],
                custom_message
            )

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(input_password, stored_password):
    return hash_password(input_password) == stored_password

def admin_login():
    st.sidebar.title("Admin Login")
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Login"):
        if username == ADMIN_USERNAME and verify_password(password, ADMIN_PASSWORD):
            st.session_state.admin_logged_in = True
            st.sidebar.success("Logged in successfully")
        else:
            st.sidebar.error("Invalid credentials")

def admin_dashboard():
    st.title("Admin Dashboard")

    # Subscriber statistics
    subscribers = get_subscribers()
    df = pd.DataFrame(subscribers, columns=['Name', 'Email', 'Keywords', 'Timestamp'])
    st.subheader("Subscriber Statistics")
    st.write(f"Total subscribers: {len(subscribers)}")
    
    # Keyword distribution
    keyword_counts = df['Keywords'].str.split(',', expand=True).stack().value_counts()
    fig = px.pie(values=keyword_counts.values, names=keyword_counts.index, title="Keyword Distribution")
    st.plotly_chart(fig)

    # Custom message for newsletter
    st.subheader("Set Custom Message for Newsletter")
    custom_message = st.text_area("Enter custom message", "")
    if st.button("Update Custom Message"):
        # Save custom message to Google Sheets
        service = get_google_sheets_service()
        sheet = service.spreadsheets()
        values = [[custom_message, str(datetime.now())]]
        body = {'values': values}
        sheet.values().update(spreadsheetId=SPREADSHEET_ID, range='CustomMessage!A2:B2', 
                              valueInputOption='USER_ENTERED', body=body).execute()
        st.success("Custom message updated successfully")

    # Manual newsletter send
    if st.button("Send Newsletters Now"):
        send_daily_newsletters(custom_message)
        st.success("Newsletters sent successfully")

def main():
    if 'admin_logged_in' not in st.session_state:
        st.session_state.admin_logged_in = False

    if not st.session_state.admin_logged_in:
        admin_login()

    if st.session_state.admin_logged_in:
        admin_dashboard()
    else:
        st.title("AI and Startup News Aggregator")

        # Display current news
        st.header("Today's Top News")
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("AI News")
            ai_news = crawl_news("AI", 5)
            for news in ai_news:
                st.write(f"- [{news['title']}]({news['link']})")
        
        with col2:
            st.subheader("Startup News")
            startup_news = crawl_news("startup", 5)
            for news in startup_news:
                st.write(f"- [{news['title']}]({news['link']})")

        # Newsletter subscription form
        st.header("Subscribe to our newsletter")
        name = st.text_input("Name")
        email = st.text_input("Email")
        keywords = st.multiselect("Select your interests", ["AI", "startup"])
        
        if st.button("Subscribe"):
            if name and email and keywords:
                save_subscriber(name, email, keywords)
                st.success("You've successfully subscribed to the newsletter!")
            else:
                st.error("Please fill in all fields")

if __name__ == "__main__":
    main()
    
    # Schedule daily newsletter
    schedule.every().day.at("11:00").do(send_daily_newsletters, "")
    
    while True:
        schedule.run_pending()
        time.sleep(1)