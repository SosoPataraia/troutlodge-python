# core/ml_model.py
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
import joblib
from django.utils import timezone
from .models import CustomerEvent, Order

class ReliabilityModel:
    def __init__(self):
        self.model = LinearRegression()
        self.scaler = StandardScaler()
        self.model_path = 'reliability_model.joblib'
        self.scaler_path = 'scaler.joblib'

    def extract_features(self, user):
        """Extract features from CustomerEvent and Order data for a user."""
        events = CustomerEvent.objects.filter(user=user)
        orders = Order.objects.filter(customer=user)

        # Feature 1: Number of logins
        login_count = events.filter(event_type='LOGIN').count()

        # Feature 2: Number of orders
        order_count = orders.count()

        # Feature 3: Timely payments (down payments made before deadline)
        timely_payments = 0
        for order in orders.filter(status__in=['down_paid', 'confirmed', 'shipped']):
            if order.downpayment_deadline and order.downpayment_proof:
                # Check if down payment was uploaded before deadline
                down_payment_event = events.filter(
                    event_type='DOWN_PAYMENT_UPLOADED',
                    order=order
                ).first()
                if down_payment_event and down_payment_event.timestamp <= order.downpayment_deadline:
                    timely_payments += 1

        # Feature 4: Completed orders
        completed_orders = orders.filter(status='shipped').count()

        return {
            'login_count': login_count,
            'order_count': order_count,
            'timely_payments': timely_payments,
            'completed_orders': completed_orders
        }

    def train(self, users):
        """Train the model using data from all customers."""
        X = []
        y = []
        for user in users:
            features = self.extract_features(user)
            X.append([
                features['login_count'],
                features['order_count'],
                features['timely_payments'],
                features['completed_orders']
            ])
            y.append(user.reliability_score)  # Use current score as target (supervised)

        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)

        # Save model and scaler
        joblib.dump(self.model, self.model_path)
        joblib.dump(self.scaler, self.scaler_path)

    def predict(self, user):
        """Predict reliability score for a user."""
        try:
            self.model = joblib.load(self.model_path)
            self.scaler = joblib.load(self.scaler_path)
        except FileNotFoundError:
            # If model not trained, return default score
            return 0.8

        features = self.extract_features(user)
        X = [[
            features['login_count'],
            features['order_count'],
            features['timely_payments'],
            features['completed_orders']
        ]]
        X_scaled = self.scaler.transform(X)
        score = self.model.predict(X_scaled)[0]
        # Ensure score is between 0 and 1
        return max(0.0, min(1.0, float(score)))