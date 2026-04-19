import yfinance as yf
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# Fetch data
stock = yf.Ticker("MSFT")
history = stock.history(period="2y")

# Calculate indicators
history["MA50"] = history["Close"].rolling(window=50).mean()
history["MA200"] = history["Close"].rolling(window=200).mean()

delta = history["Close"].diff()
gain = delta.where(delta > 0, 0)
loss = -delta.where(delta < 0, 0)
avg_gain = gain.rolling(window=14).mean()
avg_loss = loss.rolling(window=14).mean()
rs = avg_gain / avg_loss
history["RSI"] = 100 - (100 / (1 + rs))

# Create the label - 1 if price went up next day, 0 if it went down
history["Target"] = (history["Close"].shift(-1) > history["Close"]).astype(int)

# Drop rows with missing values
history.dropna(inplace=True)


# Features and label
features = ["Close", "MA50", "MA200", "RSI"]
X = history[features]
y = history["Target"]

# Split into training and testing sets
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train the model
model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Test the model
predictions = model.predict(X_test)
accuracy = accuracy_score(y_test, predictions)

print(f"Model Accuracy: {accuracy * 100:.2f}%")
# Feature importance
importance = model.feature_importances_
for feature, score in zip(features, importance):
    print(f"{feature}: {score * 100:.2f}%")

# Predict today
latest = pd.DataFrame([history[features].iloc[-1]], columns=features)
prediction = model.predict(latest)

print("\n--- ML PREDICTION ---")
if prediction[0] == 1:
    print("ML Signal: UP tomorrow 📈")
else:
    print("ML Signal: DOWN tomorrow 📉")