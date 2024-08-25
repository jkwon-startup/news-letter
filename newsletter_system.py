import streamlit as st
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import schedule
import time
from datetime import datetime
import pandas as pd
import plotly.express as px
import json

# Streamlit 페이지 설정
st.set_page_config(page_title="AI 및 1인 창업 뉴스 애그리게이터", layout="wide")

# Google Sheets API 설정
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
SPREADSHEET_ID = st.secrets["SPREADSHEET_ID"]

# 이메일 설정
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = st.secrets["SENDER_EMAIL"]
SENDER_PASSWORD = st.secrets["SENDER_PASSWORD"]

# 관리자 인증 정보
ADMIN_USERNAME = st.secrets["ADMIN_USERNAME"]
ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]

def get_google_sheets_service():
    creds_dict = json.loads(st.secrets["GOOGLE_SHEETS_CREDENTIALS"])
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
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
    msg['Subject'] = "일일 AI 및 1인 창업 뉴스"

    body = f"""
    안녕하세요 {subscriber['name']}님,

    {custom_message}

    오늘의 뉴스 업데이트입니다:

    AI 뉴스:
    """
    for news in ai_news:
        body += f"- {news['title']}\n  {news['link']}\n\n"
    
    body += "\n1인 창업 뉴스:\n"
    for news in startup_news:
        body += f"- {news['title']}\n  {news['link']}\n\n"

    msg.attach(MIMEText(body, 'plain'))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)

def send_daily_newsletters(custom_message):
    ai_news = crawl_news("AI", 5)
    startup_news = crawl_news("1인 창업", 5)
    subscribers = get_subscribers()
    
    for subscriber in subscribers:
        keywords = subscriber[2].split(',')
        if 'AI' in keywords or '1인 창업' in keywords:
            send_newsletter(
                {'name': subscriber[0], 'email': subscriber[1]},
                ai_news if 'AI' in keywords else [],
                startup_news if '1인 창업' in keywords else [],
                custom_message
            )

def verify_password(input_password, stored_password):
    return input_password == stored_password

def admin_login():
    st.sidebar.title("관리자 로그인")
    username = st.sidebar.text_input("사용자명")
    password = st.sidebar.text_input("비밀번호", type="password")
    if st.sidebar.button("로그인"):
        # 디버그 정보 출력
        st.sidebar.write(f"입력된 사용자명: {username}")
        st.sidebar.write(f"저장된 사용자명: {ADMIN_USERNAME}")
        st.sidebar.write(f"비밀번호 일치: {verify_password(password, ADMIN_PASSWORD)}")
        
        if username == ADMIN_USERNAME and verify_password(password, ADMIN_PASSWORD):
            st.session_state.admin_logged_in = True
            st.sidebar.success("로그인 성공")
        else:
            st.sidebar.error("잘못된 인증 정보")

def admin_dashboard():
    st.title("관리자 대시보드")

    # 구독자 통계
    subscribers = get_subscribers()
    df = pd.DataFrame(subscribers, columns=['이름', '이메일', '키워드', '타임스탬프'])
    st.subheader("구독자 통계")
    st.write(f"총 구독자 수: {len(subscribers)}")
    
    # 키워드 분포
    keyword_counts = df['키워드'].str.split(',', expand=True).stack().value_counts()
    fig = px.pie(values=keyword_counts.values, names=keyword_counts.index, title="키워드 분포")
    st.plotly_chart(fig)

    # 뉴스레터용 커스텀 메시지
    st.subheader("뉴스레터 커스텀 메시지 설정")
    custom_message = st.text_area("커스텀 메시지 입력", "")
    if st.button("커스텀 메시지 업데이트"):
        # 구글 시트에 커스텀 메시지 저장
        service = get_google_sheets_service()
        sheet = service.spreadsheets()
        values = [[custom_message, str(datetime.now())]]
        body = {'values': values}
        sheet.values().update(spreadsheetId=SPREADSHEET_ID, range='CustomMessage!A2:B2', 
                              valueInputOption='USER_ENTERED', body=body).execute()
        st.success("커스텀 메시지가 성공적으로 업데이트되었습니다")

    # 수동 뉴스레터 발송
    if st.button("지금 뉴스레터 발송"):
        send_daily_newsletters(custom_message)
        st.success("뉴스레터가 성공적으로 발송되었습니다")

def main():
    st.write(f"ADMIN_USERNAME is set: {'ADMIN_USERNAME' in st.secrets}")
    st.write(f"ADMIN_PASSWORD is set: {'ADMIN_PASSWORD' in st.secrets}")

    if 'admin_logged_in' not in st.session_state:
        st.session_state.admin_logged_in = False

    if not st.session_state.admin_logged_in:
        admin_login()

    if st.session_state.admin_logged_in:
        admin_dashboard()
    else:
        st.title("AI 및 1인 창업 뉴스 애그리게이터")

        # 현재 뉴스 표시
        st.header("오늘의 주요 뉴스")
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("AI 뉴스")
            ai_news = crawl_news("AI", 5)
            for news in ai_news:
                st.write(f"- [{news['title']}]({news['link']})")
        
        with col2:
            st.subheader("1인 창업 뉴스")
            startup_news = crawl_news("1인 창업", 5)
            for news in startup_news:
                st.write(f"- [{news['title']}]({news['link']})")

        # 뉴스레터 구독 양식
        st.header("뉴스레터 구독하기")
        name = st.text_input("이름")
        email = st.text_input("이메일")
        keywords = st.multiselect("관심사 선택", ["AI", "1인 창업"])
        
        if st.button("구독하기"):
            if name and email and keywords:
                save_subscriber(name, email, keywords)
                st.success("뉴스레터 구독이 완료되었습니다!")
            else:
                st.error("모든 필드를 채워주세요")

if __name__ == "__main__":
    main()
    
    # 일일 뉴스레터 스케줄링
    schedule.every().day.at("11:00").do(send_daily_newsletters, "")
    
    while True:
        schedule.run_pending()
        time.sleep(1)