import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email_report(date, top_100_html, signals_html, signal_tickers="", has_filled_prices=False):
    """Sends the analysis report via email."""
    sender = os.environ.get("EMAIL_SENDER")
    password = os.environ.get("EMAIL_PASSWORD")
    receivers = os.environ.get("EMAIL_RECEIVERS")
    
    if not all([sender, password, receivers]):
        print("[!] Skipping Email: Email credentials not set in environment.")
        return

    # Create Message
    message = MIMEMultipart("alternative")
    message["Subject"] = f"📈 Stock Analysis Report - {date}"
    message["From"] = sender
    message["To"] = receivers

    # Create HTML Body
    ticker_list_html = f"<p><strong>Signal Tickers:</strong> {signal_tickers}</p>" if signal_tickers else ""
    
    footnote_html = ""
    if has_filled_prices:
        footnote_html = '<p style="color: #c9302c; font-size: 12px; font-weight: bold; margin-top: 10px;">* Note: Prices for tickers marked with * were unavailable due to Yahoo Finance API delays and have been filled using the previous day\'s close price.</p>'

    html = f"""
    <html>
      <body>
        <h2>Daily Stock Analysis: {date}</h2>
        <hr>
        <h3>[B] STOCKS MEETING ALL CONDITIONS (Signals)</h3>
        {ticker_list_html}
        {signals_html if signals_html else "<p>No signals found today.</p>"}
        <br>
        <h3>[A] TOP 100 STOCKS BY TURNOVER (Top 20)</h3>
        {top_100_html}
        {footnote_html}
        <br>
        <p style="color: gray; font-size: 12px;">This is an automated report from your GitHub Actions workflow.</p>
      </body>
    </html>
    """
    
    part = MIMEText(html, "html")
    message.attach(part)

    try:
        # Connect to Gmail SMTP
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, receivers.split(','), message.as_string())
        print(f"[+] Email report sent successfully to {receivers}!")
    except Exception as e:
        print(f"[!] Failed to send email: {e}")
