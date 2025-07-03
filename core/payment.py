# core/payment.py
class PaymentAdapter:
    """Payment adapter to handle payment processing (simulated for MVP)"""
    def request_downpayment(self, order):
        """
        Simulate requesting a down payment for an order.
        Returns a dict with success status and transaction ID.
        """
        # Simulate payment gateway response
        return {
            "success": True,
            "transaction_id": f"DP-{order.id}-{int(order.created_at.timestamp())}"
        }

    def request_full_payment(self, order):
        """
        Simulate requesting full payment for an order.
        Returns a dict with success status and transaction ID.
        """
        # Simulate payment gateway response
        return {
            "success": True,
            "transaction_id": f"FP-{order.id}-{int(order.created_at.timestamp())}"
        }

    def verify_payment(self, transaction_id):
        """
        Simulate verifying a payment by transaction ID.
        Returns True if valid, False otherwise.
        """
        # For MVP, assume all transaction IDs are valid
        return transaction_id.startswith(("DP-", "FP-"))