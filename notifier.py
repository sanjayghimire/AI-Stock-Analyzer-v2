import requests

NTFY_CHANNEL = "stocktrader2026"
NTFY_URL = f"https://ntfy.sh/{NTFY_CHANNEL}"

def send_alert(title, message, priority="high", tags=None):
    """
    Send mobile push notification
    priority: low, default, high, urgent, max
    """
    try:
        headers = {
            "Title": title.encode("utf-8"),
            "Priority": priority,
            "Tags": ",".join(tags) if tags else "chart_with_upwards_trend",
            "Content-Type": "text/plain; charset=utf-8"
        }
        response = requests.post(
            NTFY_URL,
            data    = message.encode("utf-8"),
            headers = headers
        )
        return response.status_code == 200
    except Exception as e:
        print(f"Notification error: {e}")
        return False


# -- Pre-built alert types ------------------------------------

def alert_entry(ticker, contract, premium, score):
    send_alert(
        title    = f"TRADE SIGNAL - {ticker}",
        message  = f"Buy {contract} at ${premium}\nScore: {score}/100\nOpen your app now!",
        priority = "urgent",
        tags     = ["rotating_light", "chart_with_upwards_trend"]
    )

def alert_take_profit(ticker, premium_entry, premium_now, pct_gain):
    send_alert(
        title    = f"TAKE PROFIT - {ticker}",
        message  = f"Entry: ${premium_entry} -> Now: ${premium_now}\nUp {pct_gain}% - Take money off table!",
        priority = "urgent",
        tags     = ["money_bag", "white_check_mark"]
    )

def alert_stop_loss(ticker, premium_entry, premium_now, pct_loss):
    send_alert(
        title    = f"STOP LOSS - {ticker}",
        message  = f"Entry: ${premium_entry} -> Now: ${premium_now}\nDown {pct_loss}% - EXIT NOW. No exceptions.",
        priority = "max",
        tags     = ["stop_sign", "rotating_light"]
    )

def alert_exit_signal(ticker, reason, premium_now):
    send_alert(
        title    = f"EXIT SIGNAL - {ticker}",
        message  = f"Current premium: ${premium_now}\nReason: {reason}\nDon't wait - exit now!",
        priority = "urgent",
        tags     = ["warning", "bell"]
    )

def alert_theta_warning(ticker, days_left, premium_now):
    send_alert(
        title    = f"THETA WARNING - {ticker}",
        message  = f"{days_left} days to expiry\nPremium: ${premium_now}\nTime decay accelerating - consider exiting",
        priority = "high",
        tags     = ["hourglass_flowing_sand", "warning"]
    )

def alert_scanner_found(ticker, score, contract, premium):
    send_alert(
        title    = f"SCANNER HIT - {ticker}",
        message  = f"Score: {score}/100\nContract: {contract}\nPremium: ${premium}\nCheck the app!",
        priority = "high",
        tags     = ["satellite", "eyes"]
    )

def alert_market_open():
    send_alert(
        title    = "Market Opening Soon",
        message  = "8:20 AM CST - Market opens in 10 minutes\nScanner is running. Check top setups now.",
        priority = "default",
        tags     = ["bell", "chart_with_upwards_trend"]
    )


# -- Test -----------------------------------------------------

if __name__ == "__main__":
    print("Sending test notification to your phone...")
    success = send_alert(
        title    = "Stock Analyzer Connected!",
        message  = "Your mobile alerts are working!\nYou will get notified for:\n- Entry signals\n- Exit signals\n- Stop loss alerts\n- Theta warnings",
        priority = "default",
        tags     = ["white_check_mark", "rocket"]
    )

    if success:
        print("Notification sent! Check your phone.")
    else:
        print("Failed - check your internet connection")