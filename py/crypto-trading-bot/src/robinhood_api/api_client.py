class ApiClient:
    def __init__(self, api_key, private_key):
        self.api_key = api_key
        self.private_key = private_key
        self.base_url = "https://api.robinhood.com"

    def _get_authorization_header(self, method, path, body, timestamp):
        message_to_sign = f"{self.api_key}{timestamp}{path}{method}{body}"
        signed = self.private_key.sign(message_to_sign.encode("utf-8"))
        return {
            "x-api-key": self.api_key,
            "x-signature": base64.b64encode(signed.signature).decode("utf-8"),
            "x-timestamp": str(timestamp),
        }

    def make_api_request(self, method, endpoint, body=None):
        url = f"{self.base_url}{endpoint}"
        headers = self._get_authorization_header(method, endpoint, body or "", self._get_current_timestamp())
        response = requests.request(method, url, headers=headers, json=body)
        response.raise_for_status()
        return response.json()

    def get_historical_prices(self, symbol):
        endpoint = f"/marketdata/{symbol}/historical/"
        return self.make_api_request("GET", endpoint)

    def place_order(self, order_data):
        endpoint = "/orders/"
        return self.make_api_request("POST", endpoint, order_data)

    def get_account_info(self):
        endpoint = "/accounts/"
        return self.make_api_request("GET", endpoint)

    @staticmethod
    def _get_current_timestamp():
        return int(datetime.datetime.now(tz=datetime.timezone.utc).timestamp())